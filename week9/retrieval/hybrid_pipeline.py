import sys
from pathlib import Path
_HERE=Path(__file__).resolve()
sys.path.insert(0,str(_HERE.parent))
sys.path.insert(0,str(_HERE.parent.parent/"gate"))
sys.path.insert(0,str(_HERE.parent.parent/"router"))

import company_resolution as cr
from router import route
from numeric_retriever import build_query,numeric_retrieve
from numeric_compute import compute
from prose_retriever import retrieve
from query_decompose import decompose
from prose_generate import generate

DB=str(_HERE.parent.parent.parent/"week8"/"data"/"facts.sqlite")

def _fmt_usd(v):
    if v is None:
        return "n/a"
    a=abs(v)
    if a>=1e9:
        return f"${v/1e9:.2f}B"
    if a>=1e6:
        return f"${v/1e6:.2f}M"
    return f"${v:,.0f}"

def _answer_numeric_subq(subq):
    res=cr.resolve(subq)
    r=route(subq,use_llm=False)
    nq=build_query(r,res,subq)
    out=numeric_retrieve(nq,DB)
    comp=compute(out)
    return {"subq":subq,"resolution":res,"compute":comp}

def _answer_prose_subq(subq):
    res=cr.resolve(subq)
    if res["status"]!="resolved" or not res.get("tickers"):
        return {"subq":subq,"answer":None,"declined":True,"reason":res["status"]}
    out=retrieve(subq,tickers=res["tickers"],form="10-K")
    g=generate(subq,out["parents"])
    return {"subq":subq,"answer":g["answer"],"declined":g["declined"],
            "tickers":res["tickers"]}

def answer_hybrid(question):
    subqs=decompose(question)
    numeric_results,prose_results=[],[]

    for sq in subqs:
        r=route(sq,use_llm=False)
        if r["route"]=="NUMERIC":
            numeric_results.append(_answer_numeric_subq(sq))
        else:
            prose_results.append(_answer_prose_subq(sq))
    
    lines=[]
    for nr in numeric_results:
        c=nr["compute"]
        k=c.get("kind")
        if k=="point":
            lines.append(f"{c["ticker"]} {c["concept"].replace("_"," ")}"
                         f"FY{c['fiscal_year']}:{_fmt_usd(c["value"])}")
        elif k in ("delta", "trend"):
            lines.append(f"{c['ticker']} {c['concept'].replace('_',' ')} "
                         f"{c['from_year']}->{c['to_year']}: {_fmt_usd(c['delta'])} change")
        elif k == "growth_compare":
            g = ", ".join(f"{t} {p:+.1f}%" for t, p in c["growth"].items())
            lines.append(f"Growth: winner {c['winner']} ({g})")
        elif k == "gap":
            lines.append(f"Gap: {c['larger']} vs {c['smaller']} = {_fmt_usd(c['gap'])}")
        else:
            lines.append(f"[numeric {k}/{c.get('status')} for: {nr['subq']}]")
    
    for pr in prose_results:
        if pr["declined"] or not pr["answer"]:
            lines.append(f"[no prose answer for : {pr["subq"]}]")
        else:
            lines.append(f"{pr["subq"]}\n {pr["answer"]}")
    
    return {
        "status":"ok",
        "sub_questions":subqs,
        "numeric_results":numeric_results,
        "prose_results":prose_results,
        "answer":"\n\n".join(lines),
        "question":question,
    }

if __name__ == "__main__":
    for q in [
        ("Between Chevron and ExxonMobil, which grew revenue faster from fiscal "
         "2021 to 2025, and what reasons does each give for its revenue change?"),
        "What was Apple's 2024 net income, and what risks did they flag?",
    ]:
        print("="*70)
        print("Q:", q)
        r = answer_hybrid(q)
        print(f"\nsub-questions: {len(r['sub_questions'])}  "
              f"numeric: {len(r['numeric_results'])}  prose: {len(r['prose_results'])}")
        print("\nANSWER:\n", r["answer"][:900])