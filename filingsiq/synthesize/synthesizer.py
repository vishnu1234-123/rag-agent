"""
Synthesizer — composes the final answer to the ORIGINAL question.
 
Deterministic. All arithmetic (growth rates, gaps, rankings) is computed in code
from the numeric detail dicts — NEVER by an LLM (numbers must be exact). Prose
answers are already grounded generation output; synthesis stitches them and
handles declines HONESTLY (a declined prose leg is reported as "not found", not
omitted or papered over). Prose is disclosed as sourced from the FY2025 10-K.
 
Input:  the QueryPlan + collected NumericResult[] + Answer[]
Output: HybridAnswer with a composed `synthesis` string.
"""

from __future__ import annotations

from filingsiq.contracts import(
    QueryPlan,NumericResult,Answer,HybridAnswer,PROSE_YEAR,
)

def _fmt_usd(v):
    if v is None:
        return "n/a"
    a=abs(v)
    if a>=1e9:
        return f"${v/1e9:.2f}B"
    if a>=1e6:
        return f"${v/1e6:.2f}M"
    return f"${v:.0f}"

def _growth_rate(detail):
    fv,tv=detail.get("from_value"),detail.get("to_value")
    if fv is None or tv is None or fv==0:
        return None
    return (tv-fv)/abs(fv)*100.0

def _compose_numeric(operation,numeric_results:list[NumericResult])->list[str]:
    lines=[]

    if operation=="growth_compare" and len(numeric_results)>=2:
        ranked=[]
        for nr in numeric_results:
            rate=_growth_rate(nr.detail)
            if rate is None:
                continue
            ranked.append((nr.ticker,rate,nr.detail.get("from_value"),
                nr.detail.get("to_value"),nr.detail.get("from_year"),
                nr.detail.get("to_year")))
        
        if ranked:
            ranked.sort(key=lambda x:x[1],reverse=True)
            winner=ranked[0]
            fy,ty=winner[4],winner[5]
            lines.append(
                f"{winner[0]} grew {winner[1]:+.1f}% "
                f"({_fmt_usd(winner[2])} in {fy} → {_fmt_usd(winner[3])} in {ty}), "
                f"the fastest of the set.")
            for tk,rate,fv,tv,f_,t_ in ranked[1:]:
                lines.append(f"{tk} grew {rate:+.1f}% ({_fmt_usd(fv)} → {_fmt_usd(tv)}).")
            return lines
    for nr in numeric_results:
        d=nr.detail
        k=nr.kind
        concept=(nr.concept or "").replace("_"," ")
        if nr.status not in ("ok","partial"):
            lines.append(f"{nr.ticker} {concept}: no data ({nr.status}).")
        elif k=="point":
            lines.append(f"{nr.ticker} {concept} FY{d.get('fiscal_year')}: "
                         f"{_fmt_usd(nr.value)}.")
        elif k in ("delta","trend"):
            rate=_growth_rate(d)
            rate_s=f" ({rate:+.1f}%)" if rate is not None else ""
            lines.append(
                f"{nr.ticker} {concept} {d.get('from_year')}→{d.get('to_year')}: "
                f"{_fmt_usd(d.get('from_value'))} → {_fmt_usd(d.get('to_value'))}, "
                f"a change of {_fmt_usd(nr.delta)}{rate_s}.")
        elif k=="gap":
            lines.append(f"{d.get('larger')} exceeds {d.get('smaller')} by "
                         f"{_fmt_usd(d.get('gap'))} in {concept}.")
        elif k=="ranking":
            order = ", ".join(f"{t} {_fmt_usd(v)}" for t, y, v in d.get("ordered", []))
            lines.append(f"{concept} ranking: {order}. Highest: {d.get('winner_ticker')}.")
        else:
            lines.append(f"{nr.ticker} {concept}: {k}/{nr.status}.")
    return lines

def _compose_prose(prose_answers:list[Answer])->tuple[list[str],bool]:
    lines=[]
    any_answered=False
    for a in prose_answers:
        who=a.tickers[0] if a.tickers else "the company"
        if a.declined:
            if a.reason and a.reason.startswith("prose corpus"):
                lines.append(f"For {who}: the filings covered (FY{PROSE_YEAR}) do not "
                             f"address that year.")
            else:
                lines.append(f"For {who}: the filings do not provide the specific "
                             f"reasons requested.")
        else:
            any_answered=True
            lines.append(f"{who}: {a.text.strip()}")
    return lines,any_answered

def synthesize(plan:QueryPlan,numeric_results:list[NumericResult],
                prose_answers:list[Answer])->HybridAnswer:
    if plan.rejected:
        return HybridAnswer(question=plan.original_question, synthesis="",
                            declined=True, reason=plan.reject_reason)
    
    parts=[]

    num_lines=_compose_numeric(plan.operation,numeric_results)
    if num_lines:
        parts.append("\n".join(num_lines))
    
    prose_lines,any_prose=_compose_prose(prose_answers)
    if prose_lines:
        parts.append("\n".join(prose_lines))
        if any_prose:
            parts.append(f"(Narrative drawn from FY{PROSE_YEAR} 10-K filings.)")
    synthesis = "\n\n".join(parts) if parts else "No answerable content was found."
    declined = not parts or (not num_lines and not any_prose)

    return HybridAnswer(
        question=plan.original_question,
        synthesis=synthesis,
        numeric_results=numeric_results,
        prose_answers=prose_answers,
        declined=declined,
        reason=None if not declined else "no_grounded_content",
    )

if __name__ == "__main__":
    from filingsiq.pipeline.pipeline import answer as run_pipeline
 
    tests = [
        "What was Bank of America's total revenue in 2023?",
        "What was Apple's 2024 net income, and what risks did they flag?",
        "Between Chevron and ExxonMobil, which grew revenue faster from fiscal "
        "2021 to 2025, and what reasons does each give for its revenue change?",
        "What risks does Netflix face?",
    ]
    for q in tests:
        plan, nums, proses = run_pipeline(q)
        ha = synthesize(plan, nums, proses)
        print("=" * 74)
        print("Q:", q)
        if ha.declined and not ha.synthesis:
            print("  DECLINED:", ha.reason)
        else:
            print(ha.synthesis)
        print()
 

