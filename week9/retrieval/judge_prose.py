"""
LLM-as-judge faithfulness + correctness for grounded prose generation.
Judges MEANING (not word-overlap). Uses eval ticker (bypasses gate).
Run:  python3 week9/retrieval/judge_prose.py [n]
"""
import sys, json
from pathlib import Path
from dotenv import load_dotenv

HERE = Path(__file__).resolve()
load_dotenv(HERE.parent.parent.parent / ".env"); load_dotenv()
sys.path.insert(0, str(HERE.parent))
from openai import OpenAI
from prose_retriever import retrieve
from prose_generate import generate, _build_context
import os
_RERANK=os.environ.get("RERANK")=="1"
if _RERANK:
    from prose_rerank import rerank

_oai = OpenAI()
JUDGE_MODEL = "gpt-4o-mini"
EVAL = HERE.parent.parent.parent / "week8" / "eval" / "prose_eval.json"

# Anchored rubric — the 1/5 definitions make scores CONSISTENT across questions.
_JUDGE = (
    "You evaluate a RAG system's answer about SEC filings. You are given "
    "PASSAGES, QUESTION, SYSTEM ANSWER, and REFERENCE ANSWER.\n\n"
    "Work in steps:\n"
    "1. Break the SYSTEM ANSWER into its distinct factual claims.\n"
    "2. For EACH claim, decide if it is SUPPORTED by the passages (the claim's "
    "substance appears in the passages) or NOT SUPPORTED.\n"
    "3. faithfulness = fraction of claims supported, mapped to 1-5:\n"
    "   5 = all claims supported; 4 = >=80%; 3 = >=60%; 2 = >=40%; 1 = <40%.\n"
    "   A claim that ADDS specific detail found in the passages is SUPPORTED, "
    "not a violation. Only unsupported/invented claims count against it.\n"
    "4. correctness = does the answer address the QUESTION consistent with the "
    "REFERENCE? 5 = fully correct+complete; 4 = correct, minor omission; "
    "3 = partially correct or answers a related but different angle; "
    "2 = mostly off; 1 = wrong/irrelevant.\n"
    "   Judge correctness by MEANING, not wording. An answer grounded in a "
    "different-but-valid passage than the reference is still correct if it "
    "answers the question.\n\n"
    "Respond ONLY as JSON: "
    '{"n_claims":N,"n_supported":N,"faithfulness":N,"correctness":N}'
)


def judge(question, answer, passages_text, reference):
    user = (f"PASSAGES:\n{passages_text[:6000]}\n\nQUESTION: {question}\n\n"
            f"SYSTEM ANSWER: {answer}\n\nREFERENCE ANSWER: {reference}")
    resp = _oai.chat.completions.create(
        model=JUDGE_MODEL, temperature=0,
        response_format={"type": "json_object"},
        messages=[{"role": "system", "content": _JUDGE},
                  {"role": "user", "content": user}])
    d = json.loads(resp.choices[0].message.content.strip())
    return int(d["faithfulness"]), int(d["correctness"])


def main():
    data = json.load(open(EVAL))
    limit = int(sys.argv[1]) if len(sys.argv) > 1 else len(data)
    data = data[:limit]

    faith, corr = [], []
    declined = 0
    errored = 0
    notes = []

    for i, it in enumerate(data, 1):
        q, tk, ref = it["question"], it["ticker"], it.get("reference_answer", "")
        try:
            out = retrieve(q, tickers=tk, top_k=10)
            parents=rerank(q,out["parents"]) if _RERANK else out["parents"]
            g = generate(q, out["parents"])
            if g["declined"]:
                declined += 1
                notes.append((it["id"], "GEN-DECLINE"))
            else:
                ptext = _build_context(out["parents"])
                f, c = judge(q, g["answer"], ptext, ref)
                faith.append(f)
                corr.append(c)
                if f <= 3 or c <= 3:
                    notes.append((it["id"], f"faith={f} corr={c}"))
        except Exception as exc:
            errored += 1
            notes.append((it["id"], f"ERROR {type(exc).__name__}: {exc}"))
        if i % 10 == 0:
            print(f"  ...{i}/{len(data)}")

    n = len(faith)
    fmean = sum(faith) / n if n else 0
    cmean = sum(corr) / n if n else 0
    f4 = sum(1 for x in faith if x >= 4)
    c4 = sum(1 for x in corr if x >= 4)

    print(f"\n=== LLM-judge (n={len(data)}, scored={n}) ===")
    print(f"faithfulness: mean={fmean:.2f}/5   >=4: {f4}/{n}")
    print(f"correctness : mean={cmean:.2f}/5   >=4: {c4}/{n}")
    print(f"declines: {declined}   errors: {errored}")
    print("\nnotes (low / decline / error):")
    for rid, s in notes[:20]:
        print(f"  {rid}: {s}")


if __name__ == "__main__":
    main()