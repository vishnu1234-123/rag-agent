import os, json
from dotenv import load_dotenv
load_dotenv()
from openai import OpenAI
from filingsiq.retrieve.prose import retrieve, embed_query, _fetch_parents
from filingsiq.retrieve.rerank import rerank
from filingsiq.config import INDEX_NAME, NAMESPACE
from pinecone import Pinecone

_oai = OpenAI()
_pc = Pinecone(api_key=os.environ["PINECONE_API_KEY"])
_index = _pc.Index(INDEX_NAME)
MODEL = "gpt-4o-mini"
BANK = "week8/eval/prose_eval.json"
OUT = "rerank_quality_results.json"
WIDE = 25
TOPK = 5


def rewrite_query(q):
    r = _oai.chat.completions.create(model=MODEL, temperature=0, messages=[
        {"role": "system", "content":
         "Rewrite the user's question as a short declarative statement phrased the "
         "way a 10-K filing would state the underlying fact, so it matches filing "
         "text for retrieval. Under 40 words. Output ONLY the rewritten query."},
        {"role": "user", "content": q}])
    return r.choices[0].message.content.strip()


def _wide_retrieve(vec, ticker, top_k=WIDE):
    res = _index.query(vector=vec, top_k=top_k, namespace=NAMESPACE,
                       include_metadata=True, filter={"ticker": ticker, "form": "10-K"})
    order, best = [], {}
    for m in res["matches"]:
        pid = m["metadata"].get("parent_id")
        if pid and pid not in best:
            order.append(pid); best[pid] = m["score"]
    rows = _fetch_parents(order)
    out = []
    for pid in order:
        row = rows.get(pid)
        if row:
            row = dict(row); row["best_score"] = best[pid]; out.append(row)
    return out


def judge_relevance(question, chunk_text):
    r = _oai.chat.completions.create(model=MODEL, temperature=0, messages=[
        {"role": "system", "content":
         "You judge whether a passage is RELEVANT to answering a question about an "
         "SEC filing. Relevant = the passage contains information that would help "
         "answer the question (not just the same company/topic in passing). "
         "Reply with exactly '1' (relevant) or '0' (not relevant)."},
        {"role": "user", "content":
         f"Question: {question}\n\nPassage:\n{chunk_text[:1500]}\n\nRelevant? (1/0):"}])
    return 1 if r.choices[0].message.content.strip().startswith("1") else 0


def precision_at_k(question, parents, k=TOPK):
    top = parents[:k]
    if not top:
        return None
    return round(sum(judge_relevance(question, p.get("text") or "") for p in top) / len(top), 4)


def main():
    items = [it for it in json.load(open(BANK)) if it.get("form") == "10-K"]
    rows = []
    for it in items:
        qid, q, tk = it["id"], it["question"], it["ticker"]
        dense = retrieve(q, tickers=tk, form="10-K")["parents"]
        p_dense = precision_at_k(q, dense)
        wide = _wide_retrieve(embed_query(q), tk)
        dense_rr = rerank(q, wide, top_k=TOPK)
        p_dense_rr = precision_at_k(q, dense_rr)
        rq = rewrite_query(q)
        wide_rw = _wide_retrieve(embed_query(rq), tk)
        rw_rr = rerank(q, wide_rw, top_k=TOPK)
        p_rw_rr = precision_at_k(q, rw_rr)
        rows.append({"id": qid, "ticker": tk, "p_dense": p_dense,
                     "p_dense_rerank": p_dense_rr, "p_rewrite_rerank": p_rw_rr})
        print(f"[{qid:24}] dense={p_dense}  dense+rr={p_dense_rr}  rw+rr={p_rw_rr}")

    def mean(k):
        v = [r[k] for r in rows if r[k] is not None]
        return round(sum(v) / len(v), 4) if v else None

    from collections import Counter
    def cmp(a, b):
        if a is None or b is None: return "n/a"
        return "better" if b > a else "worse" if b < a else "same"
    rr_vs_dense = Counter(cmp(r["p_dense"], r["p_dense_rerank"]) for r in rows)

    report = {"n": len(rows), "wide": WIDE, "top_k": TOPK,
              "mean_p_dense": mean("p_dense"),
              "mean_p_dense_rerank": mean("p_dense_rerank"),
              "mean_p_rewrite_rerank": mean("p_rewrite_rerank"),
              "dense_rerank_vs_dense": dict(rr_vs_dense), "per_item": rows}
    json.dump(report, open(OUT, "w"), indent=2)
    print("\n" + "=" * 60)
    print(f"mean precision@{TOPK}:")
    print(f"  dense            {report['mean_p_dense']}")
    print(f"  dense + rerank   {report['mean_p_dense_rerank']}")
    print(f"  rewrite + rerank {report['mean_p_rewrite_rerank']}")
    print(f"\ndense+rerank vs dense (per-question): {dict(rr_vs_dense)}")
    print(f"\nwritten -> {OUT}")


if __name__ == "__main__":
    main()
