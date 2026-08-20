"""
run_ragas_prose.py — RAGAS 0.3.x faithfulness + answer relevancy on 10-K prose.
Reference-free metrics only; context precision/recall skipped (source_chunk_ids
predate corpus re-ingestion, references not source-verifiable). 10-Q filtered out.
"""
import os, json
from dotenv import load_dotenv
load_dotenv()

from filingsiq.retrieve.prose import retrieve
from filingsiq.generate.prose_generate import generate

from ragas import EvaluationDataset, SingleTurnSample, evaluate
from ragas.metrics import Faithfulness, ResponseRelevancy
from ragas.llms import LangchainLLMWrapper
from ragas.embeddings import LangchainEmbeddingsWrapper
from langchain_openai import ChatOpenAI, OpenAIEmbeddings

BANK = "week8/eval/prose_eval.json"
OUT = "ragas_prose_results.json"


def build():
    d = json.load(open(BANK))
    items = [it for it in d if it.get("form") == "10-K"]
    print(f"{len(items)} 10-K items (filtered out {len(d)-len(items)} 10-Q)\n")
    answered, declined = [], []
    for it in items:
        qid, q, tk = it["id"], it["question"], it["ticker"]
        out = retrieve(q, tickers=tk, form="10-K")
        parents = out["parents"]
        contexts = [p["text"] for p in parents if p.get("text")]
        g = generate(q, parents)
        if g["declined"] or not contexts:
            declined.append({"id": qid, "ticker": tk,
                             "reason": "declined" if g["declined"] else "no_contexts"})
            print(f"  DECLINE [{qid}] {tk}")
            continue
        answered.append((qid, tk, SingleTurnSample(
            user_input=q, response=g["answer"], retrieved_contexts=contexts)))
        print(f"  ok      [{qid}] {tk} | {len(contexts)} ctx")
    return answered, declined


def main():
    if not os.environ.get("OPENAI_API_KEY"):
        raise SystemExit("OPENAI_API_KEY not set")
    answered, declined = build()
    print(f"\nanswered {len(answered)} | declined {len(declined)}")

    ds = EvaluationDataset(samples=[s for _, _, s in answered])
    llm = LangchainLLMWrapper(ChatOpenAI(model="gpt-4o-mini", temperature=0))
    emb = LangchainEmbeddingsWrapper(OpenAIEmbeddings(model="text-embedding-3-small"))

    print("\nscoring faithfulness + answer_relevancy (a few minutes)...")
    res = evaluate(dataset=ds, metrics=[Faithfulness(), ResponseRelevancy()],
                   llm=llm, embeddings=emb)

    df = res.to_pandas()
    mcols = [c for c in df.columns if df[c].dtype.kind in "fc"]
    means = {c: round(float(df[c].mean()), 4) for c in mcols}
    report = {
        "n_total": len(answered) + len(declined),
        "n_answered": len(answered), "n_declined": len(declined),
        "decline_rate": round(len(declined)/max(1,len(answered)+len(declined)), 4),
        "metrics_run": mcols, "metric_means": means,
        "metric_n": {c: int(df[c].notna().sum()) for c in mcols},
        "skipped_metrics": ["context_precision", "context_recall"],
        "skip_reason": "source_chunk_ids predate corpus re-ingestion; references not source-verifiable",
        "declined_items": declined,
        "per_item": [
            {"id": qid, "ticker": tk,
             **{c: (None if df.iloc[i][c] != df.iloc[i][c] else round(float(df.iloc[i][c]),4))
                for c in mcols}}
            for i, (qid, tk, _) in enumerate(answered)],
    }
    json.dump(report, open(OUT, "w"), indent=2)
    print("\n=== RESULTS (10-K prose) ===")
    print(f"answered {report['n_answered']}/{report['n_total']} "
          f"(decline rate {report['decline_rate']:.1%})")
    for m, v in means.items():
        print(f"  {m:22} {v:.4f}  (n={report['metric_n'][m]})")
    print(f"\nwritten -> {OUT}")


if __name__ == "__main__":
    main()
