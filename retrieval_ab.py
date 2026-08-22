"""
retrieval_ab.py — A/B test 3 retrieval strategies on 10-K prose.
Arms (same dense index, only the QUERY differs):
  dense   : baseline (question as-is)
  rewrite : LLM rewrites question -> declarative filing-style query -> dense
  hyde    : LLM writes hypothetical answer passage, embed THAT -> dense
Primary: decline rate per arm (all / abstract / factual).
Secondary: faithfulness per arm on answered items.
"""
import os, json, re
from dotenv import load_dotenv
load_dotenv()

from openai import OpenAI
from filingsiq.retrieve.prose import retrieve, embed_query, _fetch_parents
from filingsiq.generate.prose_generate import generate
from filingsiq.config import INDEX_NAME, NAMESPACE, PARENT_PER_QUERY
from pinecone import Pinecone

from ragas import EvaluationDataset, SingleTurnSample, evaluate
from ragas.metrics import Faithfulness
from ragas.llms import LangchainLLMWrapper
from ragas.embeddings import LangchainEmbeddingsWrapper
from langchain_openai import ChatOpenAI, OpenAIEmbeddings

_oai = OpenAI()
_pc = Pinecone(api_key=os.environ["PINECONE_API_KEY"])
_index = _pc.Index(INDEX_NAME)
MODEL = "gpt-4o-mini"
BANK = "week8/eval/prose_eval.json"
OUT = "retrieval_ab_results.json"
_ABS = re.compile(r"\b(how|why|consequences|impact|affect|influenc|could|factors)\b", re.I)


def rewrite_query(q):
    r = _oai.chat.completions.create(model=MODEL, temperature=0, messages=[
        {"role": "system", "content":
         "Rewrite the user's question as a short declarative statement phrased the "
         "way a 10-K filing would state the underlying fact, so it matches filing "
         "text for retrieval. Under 40 words. Output ONLY the rewritten query."},
        {"role": "user", "content": q}])
    return r.choices[0].message.content.strip()


def hyde_passage(q):
    r = _oai.chat.completions.create(model=MODEL, temperature=0, messages=[
        {"role": "system", "content":
         "Write a short hypothetical passage (3-5 sentences) as it might appear in a "
         "company's 10-K, that directly answers the question. Declarative filing-style "
         "prose. Do not say you are hypothesizing."},
        {"role": "user", "content": q}])
    return r.choices[0].message.content.strip()


def _query_with_vector(vec, ticker, top_k=PARENT_PER_QUERY):
    res = _index.query(vector=vec, top_k=top_k, namespace=NAMESPACE,
                       include_metadata=True, filter={"ticker": ticker, "form": "10-K"})
    order, best = [], {}
    for m in res["matches"]:
        pid = m["metadata"].get("parent_id")
        if pid and pid not in best:
            order.append(pid); best[pid] = m["score"]
    rows = _fetch_parents(order)
    parents = []
    for pid in order:
        row = rows.get(pid)
        if row:
            row = dict(row); row["best_score"] = best[pid]; parents.append(row)
    return parents


def retrieve_arm(arm, q, ticker):
    if arm == "dense":
        return retrieve(q, tickers=ticker, form="10-K")["parents"], q
    if arm == "rewrite":
        rq = rewrite_query(q); return _query_with_vector(embed_query(rq), ticker), rq
    if arm == "hyde":
        hp = hyde_passage(q); return _query_with_vector(embed_query(hp), ticker), hp[:120]


def main():
    items = [it for it in json.load(open(BANK)) if it.get("form") == "10-K"]
    arms = ["dense", "rewrite", "hyde"]
    rows = []
    faith_samples = {a: [] for a in arms}

    for it in items:
        qid, q, tk = it["id"], it["question"], it["ticker"]
        abstract = bool(_ABS.search(q))
        row = {"id": qid, "ticker": tk, "abstract": abstract}
        for a in arms:
            parents, used = retrieve_arm(a, q, tk)
            contexts = [p["text"] for p in parents if p.get("text")]
            g = generate(q, parents)
            row[a] = {"declined": g["declined"], "n_ctx": len(contexts), "query_used": used}
            if not g["declined"] and contexts:
                faith_samples[a].append(SingleTurnSample(
                    user_input=q, response=g["answer"], retrieved_contexts=contexts))
        rows.append(row)
        flags = " ".join(f"{a}={'D' if row[a]['declined'] else 'a'}" for a in arms)
        print(f"[{qid:24}] abs={int(abstract)} | {flags}")

    llm = LangchainLLMWrapper(ChatOpenAI(model=MODEL, temperature=0))
    emb = LangchainEmbeddingsWrapper(OpenAIEmbeddings(model="text-embedding-3-small"))
    faith_mean = {}
    for a in arms:
        s = faith_samples[a]
        if not s:
            faith_mean[a] = None; continue
        print(f"\nscoring faithfulness arm={a} (n={len(s)})...")
        res = evaluate(dataset=EvaluationDataset(samples=s), metrics=[Faithfulness()],
                       llm=llm, embeddings=emb)
        df = res.to_pandas()
        col = [c for c in df.columns if df[c].dtype.kind in "fc"][0]
        faith_mean[a] = round(float(df[col].mean()), 4)

    def stats(pred):
        sub = [r for r in rows if pred(r)]; n = len(sub)
        return n, {a: {"declined": sum(1 for r in sub if r[a]["declined"]),
                       "decline_rate": round(sum(1 for r in sub if r[a]["declined"])/n, 4) if n else None}
                   for a in arms}

    n_all, s_all = stats(lambda r: True)
    n_abs, s_abs = stats(lambda r: r["abstract"])
    n_fac, s_fac = stats(lambda r: not r["abstract"])
    recovered = {a: [r["id"] for r in rows if r["dense"]["declined"] and not r[a]["declined"]]
                 for a in arms if a != "dense"}
    broke = {a: [r["id"] for r in rows if not r["dense"]["declined"] and r[a]["declined"]]
             for a in arms if a != "dense"}

    json.dump({"n_total": n_all, "n_abstract": n_abs, "n_factual": n_fac,
               "decline_all": s_all, "decline_abstract": s_abs, "decline_factual": s_fac,
               "faithfulness_by_arm": faith_mean, "recovered_vs_dense": recovered,
               "broke_vs_dense": broke, "per_item": rows}, open(OUT, "w"), indent=2)

    print("\n" + "=" * 60)
    print("DECLINE RATE (lower=better)   all / abstract / factual")
    for a in arms:
        print(f"  {a:8} {s_all[a]['decline_rate']:.3f} / {s_abs[a]['decline_rate']:.3f} / {s_fac[a]['decline_rate']:.3f}")
    print("\nFAITHFULNESS (answered items)")
    for a in arms:
        print(f"  {a:8} {faith_mean[a]}")
    print("\nRECOVERED vs dense:")
    for a, ids in recovered.items():
        print(f"  {a}: {ids or 'none'}")
    print("BROKE vs dense:")
    for a, ids in broke.items():
        print(f"  {a}: {ids or 'none'}")
    print(f"\nwritten -> {OUT}")


if __name__ == "__main__":
    main()
