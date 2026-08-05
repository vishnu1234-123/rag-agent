"""
Grade the router against the eval set.
 
Runs route() over every question in the four category files, compares the
predicted route to the eval's expected_route, and reports:
  - overall accuracy
  - per-route precision/recall (a confusion matrix)
  - the CRITICAL check: did any HYBRID question leak into NUMERIC/CONCEPTUAL?
    (a confident half-answer is the worst failure mode, so it's called out)
 
Runs with --no-llm by default so the deterministic rule core can be graded
with no API key. Pass --llm to exercise Tier 3.
 
Usage:
  python test_router.py --eval-dir ../../week8/eval
  python test_router.py --eval-dir ../../week8/eval --llm
"""

import argparse
import json
import os
import sys
from collections import defaultdict

from router import route,ROUTES

EVAL_FILES = [
    "numeric_eval.json",
    "decline_router.json",      # was decline_eval.json — now only router-owned rejects
    "prose_eval.json",
    "cc_hybrid_final.json",
]

def load_eval(eval_dir):
    items=[]
    for fn in EVAL_FILES:
        path=os.path.join(eval_dir,fn)
        if not os.path.exists(path):
            print(f"WARNING: {path} not found, skipping",file=sys.stderr)
            continue
        data=json.load(open(path))
        for it in data:
            exp=it.get("expected_route")
            if exp not in ROUTES:
                print(f"WARNING: {it.get('id')} has expected_route={exp!r} "
                      f"(not in {ROUTES}) — skipping", file=sys.stderr)
                continue
            items.append({"id": it["id"], "question": it["question"],
                          "expected": exp, "file": fn})
    return items

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--eval-dir",default="../../week8/eval")
    ap.add_argument("--llm",action="store_true",help="exercise Tier 3 (needs OPENAI_API_KEY)")
    ap.add_argument("--model",default="gpt-4o-mini")
    ap.add_argument("--show-errors",action="store_true",
                    help="print each misrouted question")
    args=ap.parse_args()

    items=load_eval(args.eval_dir)

    if not items:
        print("ERROR: no eval items loaded - check --eval-dir",file=sys.stderr)
        sys.exit()
    client=None

    if args.llm:
        try:
            from openai import OpenAI
        except ImportError:
            print("ERROR: pip install openai (or drop --llm)",file=sys.stderr)
        if not os.getenv("OPENAI_API_KEY"):
            print("ERROR: OPENAI_API_KEY not set (or drop --llm)",file=sys.stderr)
            sys.exit(1)
        client=OpenAI()
    
    confusion=defaultdict(lambda:defaultdict(int))
    tier_counts=defaultdict(int)
    errors=[]
    hybrid_leaks=[]

    for it in items:
        r=route(it["question"],client=client,model=args.model,
        use_llm=args.llm)
        pred=r["route"]
        confusion[it["expected"]][pred]+=1
        tier_counts[r["tier"]]+=1
        if pred!=it["expected"]:
            errors.append((it,pred,r["tier"]))
            if it["expected"]=="HYBRID" and pred in ("NUMERIC","CONCEPTUAL"):
                hybrid_leaks.append((it,pred))
    
    total=len(items)
    correct=sum(confusion[e][e] for e in ROUTES)
    print(f"\n=== Router accuracy: {correct}/{total} "
            f"({100*correct/total:.1f}%)===\n")
    
    print("Pre-route breakdown: ")
    print(f"{'route':<12} {'recall':>8} {'precision':>10} (support)")
    for r in sorted(ROUTES):
        support=sum(confusion[r].values())
        tp=confusion[r][r]
        pred_as_r=sum(confusion[e][r] for e in ROUTES)
        recall=tp/support if support else 0.0
        prec=tp/pred_as_r if pred_as_r else 0.0
        print(f" {r:<12} {recall:>7.1%} {prec:>10.1%} ({support})")
    
    print("\n Confusion (rows=expected, cols=predicted)")
    cols=sorted(ROUTES)
    print(" "+ "" * 12 + "".join(f"{c[:6]:>8}" for c in cols))
    for e in cols:
        row="".join(f"{confusion[e][p]:>8}" for p in cols)
        print(f" {e:<12}{row}")
    
    print(f"\n Tier usage: "
            + ", ".join(f"T{t}={tier_counts[t]}" for t in sorted(tier_counts)))
    
    print("\n--- Critical check: HYBRID leakage ---")
    if hybrid_leaks:
        print(f" FAIL: {len(hybrid_leaks)} HYBRID question(s) got a single-route"
                f"answer (confident half-answer)")
        
        for it,pred in hybrid_leaks:
            print(f" [{it['id']}] -> {pred}: {it['question'][:60]}")
    else:
        print(" PASS: no HYBRID question leaked into a single route.")
    
    if args.show_errors and errors:
        print("\n--- All misroutes ---")
        for it,pred,tier in errors:
            print(f"  [{it['expected']}->{pred} T{tier}] {it['id']}: "
                  f"{it['question'][:60]}")
 
    # Exit non-zero if hybrid leaks exist — makes this CI-friendly.
    sys.exit(1 if hybrid_leaks else 0)
 

if __name__ == "__main__":
    main()


