"""
retrieval_quality.py — does rewrite retrieve BETTER chunks than dense, or just
equal chunks? Measures per-chunk RELEVANCE (LLM-judged) for dense vs rewrite,
which decline rate is blind to. precision@K = fraction of top-K chunks judged
relevant. Also records dense top-1 cosine (for the cheap fallback-gate idea).
"""

import os,json
from dotenv import load_dotenv
load_dotenv()

from openai import OpenAI
from filingsiq.retrieve.prose import retrieve,embed_query,_fetch_parents
from filingsiq.config import INDEX_NAME,NAMESPACE,PARENT_PER_QUERY
from pinecone import Pinecone

_oai=OpenAI()
_pc=Pinecone(api_key=os.environ["PINECONE_API_KEY"])
_index=_pc.Index(INDEX_NAME)
MODEL="gpt-4o-mini"
BANK="week8/eval/prose_eval.json"
OUT="retrieval_quality_results.json"
TOPK=5

def rewrite_query(q):
    r=_oai.chat.completions.create(model=MODEL,temperature=0,messages=[
        {"role":"system","content":
        "Rewrite the user's question as a short declarative statement phrased the "
        "way a 10-K filing would state the underlying fact, so it matches filing "
        "text for retrieval. Under 40 words. Output ONLY the rewritten query."},
        {"role":"user","content":q}
    ])

    return r.choices[0].message.content.strip()

def _query_with_vector(vec,ticker,top_k=PARENT_PER_QUERY):
    res=_index.query(vector=vec,top_k=top_k,namespace=NAMESPACE,
                     include_metadata=True,filter={"ticker":ticker,"form":"10-K"})
    
    order,best=[],{}
    for m in res["matches"]:
        pid=m["metadata"].get("parent_id")
        if pid and pid not in best:
            order.append(pid)
            best[pid]=m["score"]
    rows=_fetch_parents(order)
    parents=[]
    for pid in order:
        row=rows.get(pid)
        if row:
            row=dict(row)
            row["best_score"]=best[pid]
            parents.append(row)
    return parents

def judge_relevance(question,chunk_text):
    r = _oai.chat.completions.create(model=MODEL, temperature=0, messages=[
        {"role": "system", "content":
         "You judge whether a passage is RELEVANT to answering a question about an "
         "SEC filing. Relevant = the passage contains information that would help "
         "answer the question (not just the same company/topic in passing). "
         "Reply with exactly '1' (relevant) or '0' (not relevant)."},
        {"role": "user", "content":
         f"Question: {question}\n\nPassage:\n{chunk_text[:1500]}\n\nRelevant? (1/0):"}])
    return 1 if r.choices[0].message.content.strip().startswith("1") else 0

def precision_at_k(question,parents,k=TOPK):
    top=parents[:k]
    if not top:
        return None,[]
    j=[judge_relevance(question,p.get("text") or "") for p in top]
    return round(sum(j)/len(j),4),j

def main():
    items=[it for it in json.load(open(BANK)) if it.get("form")=="10-K"]
    rows=[]
    for it in items:
        qid,q,tk=it["id"],it["question"],it["ticker"]
        dense=retrieve(q,tickers=tk,form="10-K")["parents"]
        rew=_query_with_vector(embed_query(rewrite_query(q)),tk)
        dp,dj=precision_at_k(q,dense)
        rp,rj=precision_at_k(q,rew)
        d1=round(dense[0]["best_score"],4) if dense else None
        v=("n/a" if rp is None or dp is None else 
            "rewrite_better" if rp>dp else "dense_better" if rp<dp else "tie")
        
        rows.append({"id": qid, "ticker": tk, "dense_p_at_k": dp, "rewrite_p_at_k": rp,
                     "dense_top1_score": d1, "verdict": v,
                     "dense_judgments": dj, "rewrite_judgments": rj})
        print(f"[{qid:24}] dense_p={dp} rew_p={rp} top1={d1} -> {v}")

        def mean(k):
            vals=[r[k] for r in rows if r[k] is not None]
            return round(sum(vals)/len(vals),4) if vals else None
        
        from collections import Counter
        verdicts=Counter(r["verdict"] for r in rows)
        wins = [r["dense_p_at_k"] for r in rows if r["verdict"] == "rewrite_better" and r["dense_p_at_k"] is not None]
    ties = [r["dense_p_at_k"] for r in rows if r["verdict"] == "tie" and r["dense_p_at_k"] is not None]

    report = {"n": len(rows), "top_k": TOPK,
              "mean_dense_p_at_k": mean("dense_p_at_k"),
              "mean_rewrite_p_at_k": mean("rewrite_p_at_k"),
              "mean_dense_top1_score": mean("dense_top1_score"),
              "verdicts": dict(verdicts),
              "avg_dense_p_where_rewrite_wins": round(sum(wins)/len(wins), 4) if wins else None,
              "avg_dense_p_where_tie": round(sum(ties)/len(ties), 4) if ties else None,
              "per_item": rows}
    json.dump(report, open(OUT, "w"), indent=2)

    print("\n" + "=" * 60)
    print(f"mean precision@{TOPK}:  dense={report['mean_dense_p_at_k']}  rewrite={report['mean_rewrite_p_at_k']}")
    print(f"mean dense top-1 cosine: {report['mean_dense_top1_score']}")
    print(f"verdicts: {dict(verdicts)}")
    print(f"\navg dense precision WHERE rewrite wins: {report['avg_dense_p_where_rewrite_wins']}")
    print(f"avg dense precision WHERE tie:          {report['avg_dense_p_where_tie']}")
    print(f"\nwritten -> {OUT}")


if __name__ == "__main__":
    main()