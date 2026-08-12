import sys
from pathlib import Path

_HERE=Path(__file__).resolve()
sys.path.insert(0,str(_HERE.parent.parent/"gate"))
sys.path.insert(0,str(_HERE.parent))

import company_resolution as cr
from prose_retriever import retrieve

def answer_prose(question,top_k=20,use_rerank=False):
    res=cr.resolve(question)
    status=res["status"]

    if status=="resolved":
        tickers=res["tickers"]
        out=retrieve(question,tickers=tickers,top_k=top_k)
        parents=out["parents"]
        if use_rerank:
            from prose_rerank import rerank
            parents=rerank(question,parents)
        return {"status":"retrieved","tickers":tickers,
                "parents":parents,"children":out["children"],
                "question":question}
    if status=="typo":
        tk,name=res["suggestion"]
        return {"status": "decline", "reason": "typo",
                "message": f"Did you mean {name.title()}?", "suggestion": res["suggestion"]}
    if status=="out_of_corpus":
        return {"status": "decline", "reason": "out_of_corpus",
                "message": "That company isn't in my coverage.",
                "names": res.get("names", [])}
    
    return {"status": "decline", "reason": "need_company",
            "message": "Which company are you asking about?"}
    
if __name__=="__main__":
    tests = [
        "What supply chain risks does Apple face?",           # resolved
        "What are the main supply chain risks?",              # need_company
        "What risks does Chevorn face?",                      # typo
        "What risks does Netflix face?",                      # out_of_corpus
    ]
    for q in tests:
        r = answer_prose(q, top_k=5)
        extra = (f"{len(r.get('parents',[]))} parents" if r["status"] == "retrieved"
                 else r.get("message"))
        print(f"{r['status']:10} | {r.get('reason',''):13} | {extra} | {q}")