"""
Pipeline orchestrator — consumes a QueryPlan, produces collected results.
 
Replaces hybrid_pipeline + prose_pipeline. Key difference from the old code:
it does NOT re-route or re-resolve each sub-question. The decomposer already
extracted ticker/concept/years/operation into structured SubQuestion fields, so
the pipeline builds the numeric query DIRECTLY from those fields and passes years
to the prose retrieval FILTER — never re-parsing text.
 
Flow:
  decompose(question) -> QueryPlan
    for each SubQuestion:
      numeric -> build nq from fields -> numeric_retrieve -> compute -> NumericResult
      prose   -> retrieve(text, ticker, years->filter) -> generate -> Answer
  -> hand (NumericResult[], Answer[], plan.operation) to synthesis (next stage)
"""

from __future__ import annotations

from filingsiq.contracts import(
    QueryPlan,SubQuestion,NumericResult,Answer,
    prose_needs_missing_filing,PROSE_YEAR,
)
from filingsiq.config import FACTS_DB
from filingsiq.decompose.decomposer import decompose
from filingsiq.retrieve.numeric import numeric_retrieve
from filingsiq.compute.numeric_compute import compute
from filingsiq.retrieve.prose import retrieve
from filingsiq.generate.prose_generate import generate, rewrite_query

DB=str(FACTS_DB)

def _nq_from_subq(sq:SubQuestion)->dict:
    """
    Build the normalized query dict numeric_retrieve expects, DIRECTLY from the
    structured SubQuestion — no router/gate roundtrip. numeric_retrieve reads:
    route, resolution.status, tickers, concept, fiscal_years.
    """

    return {
        "route":"NUMERIC",
        "tickers":[sq.ticker] if sq.ticker else [],
        "concept":sq.concept,
        "fiscal_years":list(sq.years),
        "raw_query":sq.text,
        "resolution":{"status":"resolved" if sq.ticker else "blocked",
                        "tickers":[sq.ticker] if sq.ticker else []},
    }

def _run_numeric(sq:SubQuestion)->NumericResult:
    nq=_nq_from_subq(sq)
    retrieved=numeric_retrieve(nq,DB)
    comp=compute(retrieved)

    return NumericResult(
        subq=sq.text,
        kind=comp.get("kind", "none"),
        status=comp.get("status", retrieved.get("status", "unknown")),
        value=comp.get("value"),
        delta=comp.get("delta"),
        ticker=sq.ticker or comp.get("ticker"),
        concept=sq.concept or comp.get("concept"),
        detail=comp,                      
    )

def _run_prose(sq:SubQuestion)->Answer:
    if prose_needs_missing_filing(sq.years):
        return Answer(subq=sq.text,text="",declined=True,
                      reason=f"prose corpus is FY{PROSE_YEAR} only; "
                             f"cannot answer for years {sq.years}",
                      tickers=[sq.ticker] if sq.ticker else [])
    
    if not sq.ticker:
        return Answer(subq=sq.text, text="", declined=True,
                      reason="no company resolved",
                      tickers=[])
    
    out=retrieve(sq.text,tickers=sq.ticker,form="10-K")
    g=generate(sq.text,out["parents"])
    return Answer(
        subq=sq.text,
        text=g["answer"],
        declined=g["declined"],
        reason=None if not g["declined"] else "not_found_in_filings",
        tickers=[sq.ticker],
    )

def run_plan(plan:QueryPlan)->tuple[list[NumericResult],list[Answer]]:
    numeric_results:list[NumericResult]=[]
    prose_answers:list[Answer]=[]
    for sq in plan.sub_questions:
        if sq.kind=="numeric":
            numeric_results.append(_run_numeric(sq))
        else:
            prose_answers.append(_run_prose(sq))
    return numeric_results,prose_answers

def answer(question:str):
    plan=decompose(question)
    if plan.rejected:
        return plan,[],[]
    numeric_results,prose_answers=run_plan(plan)
    return plan,numeric_results,prose_answers

if __name__ == "__main__":
    tests = [
        "What was Bank of America's total revenue in 2023?",
        "What was Apple's 2024 net income, and what risks did they flag?",
        "Between Chevron and ExxonMobil, which grew revenue faster from fiscal "
        "2021 to 2025, and what reasons does each give for its revenue change?",
        "What risks does Netflix face?",
    ]
    for q in tests:
        print("\n" + "=" * 70)
        print("Q:", q)
        plan, nums, proses = answer(q)
        if plan.rejected:
            print("  REJECTED:", plan.reject_reason)
            continue
        print("  operation:", plan.operation)
        for nr in nums:
            print(f"  [numeric] {nr.ticker} {nr.concept} kind={nr.kind} "
                  f"status={nr.status} value={nr.value} delta={nr.delta}")
        for a in proses:
            head = (a.text[:120] + "...") if a.text and len(a.text) > 120 else a.text
            print(f"  [prose  ] {a.tickers} declined={a.declined} "
                  f"reason={a.reason}\n            {head}")
 


