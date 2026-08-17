
"""
Decomposer — the SOLE extractor of the pipeline.
 
Given the original question it produces a structured QueryPlan:
  - resolves the company/companies (via the gate)
  - determines top-level operation  (markers -> LLM-enum fallback)
  - determines concept              (regex   -> LLM-enum fallback)
  - extracts years                 (deterministic)
  - splits into sub-questions in ONE LLM call, each classified numeric|prose
  - VALIDATES every enum field against contracts (coerce invalid -> None)
  - applies the prose-year guard (reject prose legs needing a non-2025 filing)
 
Downstream, the router only CONFIRMS the route per sub-question and pre-rejects
out-of-scope legs — it does not re-extract. Single source of truth for extraction.
 
Enum safety is enforced by OUR OWN validation (provider-portable), not by a
provider-specific structured-output feature. The LLM call uses plain JSON mode;
we validate the result against contracts.CONCEPTS / OPERATIONS / KINDS.
"""

from __future__ import annotations

import json
import os 
from pathlib import Path
from dotenv import load_dotenv

from openai import OpenAI

from filingsiq.contracts import(
    QueryPlan,SubQuestion,
    CONCEPTS,OPERATIONS,KINDS,CORPUS_YEARS,PROSE_YEAR,
    prose_needs_missing_filing,
)
from filingsiq.gate import company_resolution as cr
from filingsiq.router import signals

_HERE=Path(__file__).resolve()
load_dotenv(_HERE.parent.parent.parent/".env")
load_dotenv()
_oai=OpenAI()
DECOMPOSE_MODEL="gpt-4o-mini"

_OP_MARKERS = {
    "growth_compare": ("grew faster", "grow faster", "which grew", "growth", "faster", "fastest"),
    "gap":            ("how much larger", "how much bigger", "how much more", "how much smaller",
                       "difference between", "gap between", "larger than", "bigger than"),
    "rank":           ("highest", "largest", "biggest", "most", "lowest", "smallest", "least", "rank"),
}

def _detect_operation(q:str)->str|None:
    ql=q.lower()
    for op,markers in _OP_MARKERS.items():
        if any(m in ql for m in markers):
            return op
    return None

def _valid_or_none(value,allowed):
    return value if value in allowed else None

# --- the single LLM split call -----------------------------------------------
_SYSTEM = (
    "You decompose questions about SEC filings into self-contained sub-questions "
    "and classify each. Return ONLY JSON, no prose.\n\n"
    "For the WHOLE question, determine:\n"
    "  operation: one of point|delta|trend|gap|growth_compare|rank|null\n"
    "    - point: a single figure for one company/year\n"
    "    - delta/trend: one company's change across years\n"
    "    - gap: difference between two companies (same year)\n"
    "    - growth_compare: which of 2+ companies grew faster across years\n"
    "    - rank: order 2+ companies by a figure\n"
    "    - null: a pure prose question (no numeric operation)\n\n"
    "For EACH sub-question, provide:\n"
    "  text: the clean question, NO year ranges stuffed in, NO operation words needed\n"
    "  kind: 'numeric' (a figure from a database) or 'prose' (reasons/factors/risks)\n"
    "  concept: one of revenue|net_income|total_assets|null  (null if prose or unsupported)\n"
    "  company: the explicit company name for this sub-question (never 'each'/'both')\n"
    "  years: list of integers this sub-question refers to (empty if none)\n\n"
    "Rules:\n"
    "- Expand 'each'/'both' into one sub-question per company.\n"
    "- Separate a NUMERIC ask from a PROSE ask into DIFFERENT sub-questions.\n"
    "- Numeric sub-questions carry their specific year(s). Prose sub-questions ask "
    "for reasons/factors plainly.\n"
    'Return JSON exactly: {"operation": "...", "sub_questions": '
    '[{"text":"...","kind":"...","concept":"...","company":"...","years":[...]}]}'
)

def _llm_split(question:str,op_hint:str|None,concept_hint:str|None)->dict:
    hint=""
    if op_hint:
        hint += f"\n(Detected operation hint: {op_hint} — confirm or correct.)"
    if concept_hint:
        hint += f"\n(Detected concept hint: {concept_hint} — confirm or correct.)"
    resp=_oai.chat.completions.create(
        model=DECOMPOSE_MODEL,temperature=0,
        response_format={"type":"json_object"},
        messages=[{"role":"system","content":_SYSTEM},
                  {"role":"user","content":f"Question:{question}{hint}"}],
    )
    return json.loads(resp.choices[0].message.content.strip())

def decompose(question:str)->QueryPlan:
    res=cr.resolve(question)
    status=res.get("status")
    if status=="out_of_corpus":
        return QueryPlan(question,None,rejected=True,
                reject_reason=f"out_of_corpus:{res.get("names")}")
    if status=="typo":
        tk,name=res["suggestion"]
        return QueryPlan(question,None,rejected=True,
                reject_reason=f"typo: did you mean {name.title()}?")
    if status=="need_company":
        return QueryPlan(question,None,rejected=True,
                reject_reason="need_company: which company?")
    
    tickers=res.get("tickers",[])

    op_hint=_detect_operation(question)
    concept_hint=signals.extract_concept(question)

    data=_llm_split(question,op_hint,concept_hint)

    operation=_valid_or_none(data.get("operation"),OPERATIONS) or op_hint

    name_to_ticker={n:tk for tk in tickers for n in cr.CORPUS.get(tk,set())}

    sub_questions:list[SubQuestion]=[]

    for sq in data.get("sub_questions",[]):
        text=(sq.get("text") or "").strip()
        if not text:
            continue
        kind=_valid_or_none(sq.get("kind"),KINDS) or "prose"
        concept=_valid_or_none(sq.get("concept"),CONCEPTS)

        comp=(sq.get("company") or "").strip().lower()
        ticker=name_to_ticker.get(comp)
        if ticker is None and len(tickers)==1:
            ticker=tickers[0]
        years=[int(y) for y in (sq.get("years") or []) 
                if str(y).isdigit() and int(y) in CORPUS_YEARS]
        
        if kind=="prose" and prose_needs_missing_filing(years):
            sub_questions.append(SubQuestion(text=text,kind="prose",ticker=ticker,
                    concept=concept,years=years,operation=None))
            
            continue
        
        sub_op=None
        if kind == "numeric":
            sub_op = "point" if len(years) <= 1 else ("delta" if len(years) == 2 else "trend")
        sub_questions.append(SubQuestion(
            text=text, kind=kind, ticker=ticker, concept=concept,
            years=years, operation=sub_op))
        
    if not sub_questions:
        return QueryPlan(question, operation, rejected=True,
                         reject_reason="no_answerable_subquestions")
 
    return QueryPlan(original_question=question, operation=operation,
                     sub_questions=sub_questions)


if __name__ == "__main__":
    tests = [
        "Between Chevron and ExxonMobil, which grew revenue faster from fiscal "
        "2021 to 2025, and what reasons does each give for its revenue change?",
        "What was Apple's 2024 net income, and what risks did they flag?",
        "What was Bank of America's total revenue in 2023?",
        "What risks does Netflix face?",                 # out_of_corpus
    ]
    for q in tests:
        plan = decompose(q)
        print("\nQ:", q)
        if plan.rejected:
            print("  REJECTED:", plan.reject_reason)
            continue
        print("  operation:", plan.operation)
        for s in plan.sub_questions:
            print(f"    [{s.kind:7}] {s.ticker} concept={s.concept} years={s.years} "
                  f"op={s.operation} :: {s.text}")
 
