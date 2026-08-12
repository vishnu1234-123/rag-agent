"""
Validate grounded generation across all 51 prose eval questions.

Full pipeline per question: answer_prose (gate+retrieve) -> generate.
Scores the generated answer against reference_answer by content-word overlap
(same metric as retrieval validation, so numbers are comparable).

Also tracks declines: a prose eval question SHOULD be answerable (all are
subtype=grounded with a real reference), so a decline here is a miss — flags
over-strict generation.

Run from repo root:  python3 week9/retrieval/validate_prose_generation.py [threshold]
"""
import sys, json, re, statistics
from pathlib import Path

HERE = Path(__file__).resolve()
sys.path.insert(0, str(HERE.parent))
from prose_pipeline import answer_prose
from prose_generate import generate

ROOT = HERE.parent.parent.parent
EVAL = ROOT / "week8" / "eval" / "prose_eval.json"

_STOP = set("the a an and or of to in for on with as is are was were be been being "
            "their its it they this that these those which who what how according "
            "from by at into over under can could may might will would them his her "
            "our your we you has have had do does did not no primarily ultimately "
            "various company companys able ability".split())


def content_words(text):
    return {w for w in re.findall(r"[a-z0-9]+", (text or "").lower())
            if w not in _STOP and len(w) > 2}


def coverage(reference, answer):
    ref = content_words(reference)
    if not ref:
        return 0.0
    return len(ref & content_words(answer)) / len(ref)


def main():
    thresh = float(sys.argv[1]) if len(sys.argv) > 1 else 0.5
    data = json.load(open(EVAL))
    hits = declines = errors = 0
    rows = []
    for i, it in enumerate(data, 1):
        q = it["question"]
        ref = it.get("reference_answer", "")
        try:
            r = answer_prose(q, top_k=10)
            if r["status"] != "retrieved":
                declines += 1
                rows.append((it["id"], -1.0, f"PIPELINE-DECLINE {r.get('reason')}"))
                continue
            g = generate(q, r["parents"])
            if g["declined"]:
                declines += 1
                rows.append((it["id"], -1.0, "GEN-DECLINE"))
                continue
            cov = coverage(ref, g["answer"])
            if cov >= thresh:
                hits += 1
            rows.append((it["id"], cov, ""))
        except Exception as e:
            errors += 1
            rows.append((it["id"], -2.0, f"ERROR {e}"))
        if i % 10 == 0:
            print(f"  ...{i}/{len(data)}")

    n = len(data)
    print(f"\n=== generation vs reference (overlap >= {thresh}, n={n}) ===")
    print(f"HIT {hits}/{n} ({100*hits/n:.1f}%)  declines {declines}  errors {errors}")
    covs = [r[1] for r in rows if r[1] >= 0]
    if covs:
        print(f"coverage: mean={statistics.mean(covs):.2f} median={statistics.median(covs):.2f} "
              f"min={min(covs):.2f} max={max(covs):.2f}")
    rows.sort(key=lambda r: r[1])
    print("\nweakest / declines / errors:")
    for rid, cov, note in rows[:12]:
        print(f"  {cov:5.2f}  {rid}  {note}")


if __name__ == "__main__":
    main()