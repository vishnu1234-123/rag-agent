"""
Grade company_resolution.resolve() against decline_gate.json.
 
A decline question is 'handled' if resolve() returns anything that leads to a
reject-or-clarify — i.e. NOT a clean in-corpus 'resolved'. The gate's job on
these is to NOT silently answer them.
 
Breaks results down by trap subtype so a weakness in one class is visible.
"""

import json,sys
from collections import defaultdict
import company_resolution as cr

def main():
    path = sys.argv[1] if len(sys.argv) > 1 else "../../../week8/eval/decline_gate.json"
    data=json.load(open(path))

    by_sub=defaultdict(lambda : [0,0])
    misses=[]

    for it in data:
        q=it["question"]
        sub=it.get("subtype") or it.get("trap") or "?"
        res=cr.resolve(q)

        handled=res["status"]!="resolved"
        by_sub[sub][0]+=1
        by_sub[sub][1]+=handled
        if not handled:
            misses.append((it.get("id"),q,res))
    total=sum(v[0] for v in by_sub.values())
    ok=sum(v[1] for v in by_sub.values())
    print(f"\n=== Gate resolution: {ok}/{total} handled ({100*ok/total:.1f}%) ===\n")
    print(f"  {'subtype':<24}{'handled':>10}  (n)")

    for sub in sorted(by_sub):
        n,h=by_sub[sub]
        print(f"  {sub:<24}{h}/{n:<8}  {100*h/n:.0f}%")
    
    if misses:
        print(f"\n--- {len(misses)} silently resolved (should reject/clarify) ---")
        for mid, q, res in misses:
            print(f"  [{mid}] {res}")
            print(f"     {q[:60]}")
    else:
        print("\n  PASS: every gate-reject question was caught (none silently resolved).")
 
if __name__ == "__main__":
    main()