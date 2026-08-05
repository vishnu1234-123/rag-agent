"""
Run the FROZEN router against the adversarial stress set and report failures
BROKEN DOWN BY ATTACK STYLE.
 
The point is diagnosis, not a score: a low number on one style ("terse", "typo")
tells you a *class* of weakness. You then decide, deliberately, whether that class
is worth a code change — NOT by patching individual questions.
 
Discipline: do NOT tune the router to raise this number. If you change code, change
it for a systematic, explained weakness, then regenerate a FRESH stress set to
re-measure (never reuse the set you tuned against).
 
Usage:
  python stress_run.py --in stress_set.json                 # rules only
  python stress_run.py --in stress_set.json --llm           # full router
  python stress_run.py --in stress_set.json --llm --show-errors
"""

import argparse
import json
import os 
import sys
from collections import defaultdict

from router import route,ROUTES

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--in",dest="inp",default="stress_set.json")
    ap.add_argument("--llm",action="store_true")
    ap.add_argument("--model",default="gpt-4o-mini")
    ap.add_argument("--show-errors",action="store_true")
    args=ap.parse_args()

    items=json.load(open(args.inp))
    client=None

    if args.llm:
        from openai import OpenAI
        if not os.getenv("OPENAI_API_KEY"):
            print("ERROR: OPENAI_API_KEY not set",file=sys.stderr)
            sys.exit(1)
        client=OpenAI()

    
    by_style=defaultdict(lambda: [0,0])
    errors=[]
    leaks_down=[] # CRITICAL: hybrid -> single route (loses half the answer)
    leaks_up = []     # WASTEFUL: single route -> hybrid (safe but over-fetches)
    
    for it in items:
        exp=it["expected_route"]
        r=route(it["question"],client=client,model=args.model,use_llm=args.llm)
        pred=r["route"]
        style=it.get("style","?")
        by_style[style][0]+=1
        ok=(pred==exp)
        if ok:
            by_style[style][1]+=1
        else:
            errors.append((it,pred,r.get("tier")))
            if exp=="HYBRID" and pred in ("NUMERIC","CONCEPTUAL"):
                leaks_down.append((it,pred))
            elif exp in ("NUMERIC","CONCEPTUAL") and pred=="HYBRID":
                leaks_up.append((it,pred))
    
    total=sum(v[0] for v in by_style.values())
    correct=sum(v[1] for v in by_style.values())
    print(f"\n=== Stress test: {correct}/{total} ({100*correct/total:.1f}%) ===")
    print("(this is a DIAGNOSTIC, not a target — read it by style)\n")
 
    print(f"  {'style':<16}{'acc':>8}   (n)")

    for style in sorted(by_style):
        tot,cor=by_style[style]
        print(f"  {style:<16}{cor/tot:>7.1%}   ({tot})")

    print("\n--- Leak analysis (direction matters) ---")

    if leaks_down:
        print(f" CRITICAL: {len(leaks_down)} HYBRID -> single route "
                f"(loses half the answer):")
        
        for it,pred in leaks_down:
            print(f"    ->{pred}: {it["question"][:60]}")
    else:
        print(" OK: no HYBRID collapsed to a single route.")
    
    if leaks_up:
        print(f" WASTE:{len(leaks_up)} single-route -> HYBRID"
                f"(correct answer, but over-fetches - extra cost/latency):")
        for it,pred in leaks_up:
            print(f"    {it['expected_route']}->HYBRID: {it["question"][:55]}")
    else:
        print(" OK: no single-route question over-routed to HYBRID.")
    
    if args.show_errors and errors:
        print("\n--- Failures by style ---")
        cur=None
        for it,pred,tier in sorted(errors,key=lambda x:x[0].get("style","")):
            if it.get("style")!=cur:
                cur=it.get("style")
                print(f"\n [{cur}]")
            print(f" exp {it['expected_route']:<10} got {pred:<10}"
                    f"T{tier}: {it['question'][:60]}")

if __name__=="__main__":
    main()

    
