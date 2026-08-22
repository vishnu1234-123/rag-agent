"""
run_ragas.py — RAGAS 0.3.x faithfulness eval on the prose generation path.

Scores ONLY the retrieval-grounded prose items. Numeric (SQL path), rejects,
and hybrid (stitched) are excluded by design — RAGAS measures grounding of an
answer in retrieved contexts, which only the pure-prose path satisfies.

Runs the real code path: filingsiq.retrieve.prose.retrieve -> generate.
"""
import os, json
from dotenv import load_dotenv
load_dotenv()

from filingsiq.retrieve.prose import retrieve
from filingsiq.generate.prose_generate import generate

from ragas import EvaluationDataset, SingleTurnSample, evaluate
from ragas.metrics import (
    Faithfulness, ResponseRelevancy,
    LLMContextPrecisionWithReference, LLMContextRecall,
)
from ragas.llms import LangchainLLMWrapper
from ragas.embeddings import LangchainEmbeddingsWrapper
from langchain_openai import ChatOpenAI, OpenAIEmbeddings

# ticker per prose item (retrieve needs it; inline is fine for 5)
TICKERS = {
    "prose_answerable_1": "AAPL",
    "prose_answerable_2": "GOOGL",
    "prose_answerable_3": "TSLA",
    "prose_boilerplate_1": "CVX",
    "prose_scenario_cvx": "CVX",
}
# items whose expected_answer is a REAL reference (usable as `reference`)
HAS_CLEAN_REFERENCE = {"prose_answerable_1", "prose_answerable_2", "prose_answerable_3"}


def build_samples():
    items = [q for q in json.load(open("pipeline_eval.json")) if q["type"] == "prose"]
    samples = []
    for it in items:
        qid, q = it["id"], it["question"]
        tk = TICKERS[qid]
        out = retrieve(q, tickers=tk, form="10-K")
        parents = out["parents"]
        contexts = [p["text"] for p in parents if p.get("text")]
        g = generate(q, parents)
        print(f"[{qid}] {tk} | declined={g['declined']} | "
              f"{len(contexts)} contexts | ans[:80]={g['answer'][:80]!r}")
        s = SingleTurnSample(
            user_input=q,
            response=g["answer"],
            retrieved_contexts=contexts,
            reference=it["expected_answer"] if qid in HAS_CLEAN_REFERENCE else None,
        )
        samples.append(s)
    return samples


def main():
    if not os.environ.get("OPENAI_API_KEY"):
        raise SystemExit("OPENAI_API_KEY not set")

    samples = build_samples()

    llm = LangchainLLMWrapper(ChatOpenAI(model="gpt-4o-mini", temperature=0))
    emb = LangchainEmbeddingsWrapper(OpenAIEmbeddings(model="text-embedding-3-small"))

    no_ref = EvaluationDataset(samples=samples)
    r1 = evaluate(dataset=no_ref,
                  metrics=[Faithfulness(), ResponseRelevancy()],
                  llm=llm, embeddings=emb)
    print("\n=== faithfulness + response_relevancy (all 5 prose) ===")
    print(r1)

    ref_samples = [s for s in samples if s.reference]
    if ref_samples:
        with_ref = EvaluationDataset(samples=ref_samples)
        r2 = evaluate(dataset=with_ref,
                      metrics=[LLMContextPrecisionWithReference(), LLMContextRecall()],
                      llm=llm, embeddings=emb)
        print("\n=== context_precision + context_recall (3 items w/ clean reference) ===")
        print(r2)

    print("\nNOTE: boilerplate_1 / scenario_cvx excluded from context metrics — "
          "expected_answer is annotation notes, not reference prose.")


if __name__ == "__main__":
    main()
