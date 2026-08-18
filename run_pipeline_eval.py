"""
Pipeline stress-test runner.

Runs every question in pipeline_eval.json through the FULL pipeline
(decompose -> run -> synthesize), classifies what the pipeline actually DID,
and compares to expected_behavior. Reports where behavior violates expectation
so we can see where the pipeline breaks — before doing full answer verification.

Behavior classification (from the HybridAnswer + parts):
  reject   : plan.rejected (out_of_corpus / bad year / unsupported concept)
  decline  : produced but no grounded content (all legs declined)
  partial  : some legs answered, some declined
  answer   : answered with content

Expected-behavior labels in the eval set are permissive where the pipeline
legitimately has options (e.g. 'answer_or_clarify', 'decline_or_flag').
"""
import json
import sys

from filingsiq.pipeline.pipeline import answer as run_pipeline
from filingsiq.synthesize.synthesizer import synthesize


def classify(plan, nums, proses, ha):
    if plan.rejected:
        return "reject"
    n_answered = sum(1 for a in proses if not a.declined) + \
                 sum(1 for nr in nums if nr.status in ("ok", "partial"))
    n_total = len(proses) + len(nums)
    n_declined = n_total - n_answered
    if n_total == 0:
        return "decline"
    if n_answered == 0:
        return "decline"
    if n_declined > 0:
        return "partial"
    return "answer"


def matches(expected, actual):
    """Does actual behavior satisfy the expected label? (labels are permissive)"""
    e = expected
    if e == "answer":
        return actual in ("answer",)
    if e == "reject":
        return actual == "reject"
    if e in ("decline_or_flag",):
        # ideal is decline; a partial (numeric ok, prose declined) also acceptable;
        # a full 'answer' here means it answered boilerplate -> VIOLATION to inspect
        return actual in ("decline", "partial")
    if e in ("answer_numeric_maybe_decline_prose", "answer_growth_maybe_decline_prose"):
        # numeric must land; prose may decline -> answer or partial both OK
        return actual in ("answer", "partial")
    if e == "answer_or_clarify":
        return actual in ("answer", "decline", "partial")
    return None  # unknown label


def main():
    path = sys.argv[1] if len(sys.argv) > 1 else "pipeline_eval.json"
    items = json.load(open(path))
    print(f"running {len(items)} questions through the full pipeline\n")

    rows = []
    for it in items:
        q = it["question"]
        try:
            plan, nums, proses = run_pipeline(q)
            ha = synthesize(plan, nums, proses)
            actual = classify(plan, nums, proses, ha)
            err = None
        except Exception as e:
            actual = "ERROR"
            err = f"{type(e).__name__}: {e}"
            ha = None
        ok = matches(it["expected_behavior"], actual)
        rows.append({"id": it["id"], "type": it["type"],
                     "expected": it["expected_behavior"], "actual": actual,
                     "ok": ok, "err": err,
                     "synth": (ha.synthesis[:200] if ha and ha.synthesis else "")})

    # report
    print("=" * 88)
    print(f"{'id':26} {'type':22} {'expected':20} {'actual':9} verdict")
    print("=" * 88)
    for r in rows:
        v = "OK" if r["ok"] else ("?? unknown-label" if r["ok"] is None else "XX VIOLATION")
        print(f"{r['id']:26} {r['type']:22} {r['expected']:20} {r['actual']:9} {v}")
        if r["err"]:
            print(f"    ERROR: {r['err']}")

    viol = [r for r in rows if r["ok"] is False]
    errs = [r for r in rows if r["actual"] == "ERROR"]
    print("\n" + "=" * 88)
    print(f"passed {sum(1 for r in rows if r['ok'])}/{len(rows)}  |  "
          f"violations {len(viol)}  |  errors {len(errs)}")
    if viol:
        print("\nVIOLATIONS TO INSPECT:")
        for r in viol:
            print(f"  [{r['type']}] {r['id']}: expected {r['expected']}, got {r['actual']}")
            if r["synth"]:
                print(f"     synth: {r['synth']}")
    if errs:
        print("\nERRORS (pipeline crashed):")
        for r in errs:
            print(f"  {r['id']}: {r['err']}")


if __name__ == "__main__":
    main()