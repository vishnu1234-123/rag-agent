"""
Hybrid retrieval A/B test.
 
For each prose question in the eval, compares three retrieval methods over the
SAME candidate pool (all of a ticker's 10-K parents from parents.sqlite):
 
  A  dense   : current pipeline (Pinecone semantic search -> parents)
  B  bm25    : keyword ranking over ALL the ticker's 10-K parent texts (SQLite)
  C  hybrid  : Reciprocal Rank Fusion of A and B
 
Then generates from each method's top-k and reports answer/decline. Summarizes:
  - does hybrid recover misses (dense declines, hybrid answers)?
  - does hybrid BREAK any dense wins (dense answers, hybrid declines)?
  - which sections each method surfaces.
 
Dense scores (cosine ~0.6) and BM25 scores (unbounded) are different scales, so
fusion is by RANK (RRF), not raw score.
"""

import json
import sys
import sqlite3

from rank_bm25 import BM25Okapi

from filingsiq.config import PARENT_DB
from filingsiq.retrieve.prose import retrieve 
from filingsiq.generate.prose_generate import generate

TOP_K=10
RRF_K=60

def _all_parents(ticker):
    con=sqlite3.connect(str(PARENT_DB))
    rows=con.execute(
        "SELECT parent_id,section_item,text FROM parents "
        "WHERE ticker=? AND form ='10-K'",(ticker,)).fetchall()
    con.close()
    return [{"parent_id":r[0],"section_item":r[1],"text":r[2]} for r in rows]

def _tok(s):
    return (s or "").lower().split()

def dense_rank(question,ticker):
    out=retrieve(question,tickers=ticker,form="10-K")
    return out["parents"]

def bm25_rank(question,pool):
    corpus=[_tok(p["text"]) for p in pool]
    bm25=BM25Okapi(corpus)
    scores=bm25.get_scores(_tok(question))
    ranked=sorted(zip(pool,scores),key=lambda x:x[1],reverse=True)
    return [dict(p,bm25_score=float(s)) for p,s in ranked]

def rrf_fuse(dense_list,bm25_list,k=RRF_K):
    score={}
    meta={}
    for rank,p in enumerate(dense_list):
        pid=p["parent_id"]
        score[pid]=score.get(pid,0)+1.0/(k+rank)
        meta[pid]=p
    
    for rank,p in enumerate(bm25_list):
        pid=p["parent_id"]
        score[pid]=score.get(pid,0)+1.0/(k+rank)
        meta.setdefault(pid,p)
    fused=sorted(score.items(),key=lambda x:x[1],reverse=True)
    return [meta[pid] for pid,_ in fused]

def sections(parents,n=TOP_K):
    return [str(p.get("section_item","?")) for p in parents[:n]]

def run_question(q,ticker):
    pool=_all_parents(ticker)
    dense=dense_rank(q,ticker)
    bm25=bm25_rank(q,pool)
    hybrid=rrf_fuse(dense,bm25)

    results={}
    for name, parents in [("dense", dense), ("bm25", bm25), ("hybrid", hybrid)]:
        g = generate(q, parents[:TOP_K])
        results[name] = {
            "declined": g["declined"],
            "sections": sections(parents),
            "answer_head": (g["answer"][:150] if not g["declined"] else ""),
        }
    return results

def main():
    path=sys.argv[1] if len(sys.argv)>1 else "pipeline_eval.json"
    items=json.load(open(path))

    prose_qs=[]
    for it in items:
        if it["type"] in ("prose",):
            # infer ticker from the question (simple: known names)
            prose_qs.append(it)
 
    # ticker inference for the prose questions in this eval
    Q_TICKER = {
        "prose_answerable_1": ("What supply chain risks does Apple describe?", "AAPL"),
        "prose_answerable_2": ("What does Alphabet say about how it attracts and retains advertisers?", "GOOGL"),
        "prose_answerable_3": ("What competitive risks does Tesla identify?", "TSLA"),
        "prose_boilerplate_1": ("What reasons does Chevron give for its revenue change?", "CVX"),
        "prose_scenario_cvx": ("What reasons does Chevron give for its revenue change?", "CVX"),
    }
 
    print("=" * 90)
    print("HYBRID A/B TEST — dense vs bm25 vs RRF-hybrid (prose questions)")
    print("=" * 90)

    summary = {"recovered": [], "broken": [], "unchanged": []}
    for it in prose_qs:
        if it["id"] not in Q_TICKER:
            continue
        q, ticker = Q_TICKER[it["id"]]
        res = run_question(q, ticker)
        print(f"\n[{it['id']}] {ticker}: {q}")
        for name in ("dense", "bm25", "hybrid"):
            r = res[name]
            verdict = "DECLINED" if r["declined"] else "answered"
            print(f"   {name:7} {verdict:9} sections={r['sections'][:6]}")
        # classify: did hybrid recover a dense decline? break a dense answer?
        d_dec = res["dense"]["declined"]
        h_dec = res["hybrid"]["declined"]
        if d_dec and not h_dec:
            summary["recovered"].append(it["id"])
        elif not d_dec and h_dec:
            summary["broken"].append(it["id"])
        else:
            summary["unchanged"].append(it["id"])
 
    print("\n" + "=" * 90)
    print("SUMMARY")
    print("=" * 90)
    print(f"  hybrid RECOVERED (dense declined -> hybrid answered): {summary['recovered'] or 'none'}")
    print(f"  hybrid BROKE     (dense answered -> hybrid declined): {summary['broken'] or 'none'}")
    print(f"  unchanged: {summary['unchanged']}")
    print("\n  Decision: enable hybrid if it recovers misses AND breaks nothing.")
    print("  If it breaks some, wire as FALLBACK (dense first, hybrid on decline).")
 
 
if __name__ == "__main__":
    main()
    