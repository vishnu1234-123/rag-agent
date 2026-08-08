"""
Grade company_resolution.resolve() against the COMPANY-based decline questions.
 
IMPORTANT: resolve() only owns COMPANY resolution (out-of-corpus, typos). The
year and concept rejects (out_of_range, out_of_concept) are the ROUTER's job —
it rejects them before the gate ever runs (has_out_of_range_year,
numeric_ask_unsupported_concept). So this grader filters decline_gate.json to
the company-based subtypes only; grading resolve() against year/concept rejects
would test the wrong component and produce a misleadingly low number.
 
'handled' = resolve() did NOT clean-resolve to an in-corpus company (i.e. it
returned out_of_corpus / typo / need_company).
"""

import json,sys
from collections import defaultdict
import company_resolution as cr

COMPANY_SUBTYPES=("corpus","misspelling","typo","notco","not_co","outof")

def _is_company_subtype(sub):
    s=(sub or "").lower()
    return any(m for m in COMPANY_SUBTYPES)

def main():
    path = sys.argv[1] if len(sys.argv) > 1 else "../../../week8/eval/decline_gate.json"
    data=json.load(open(path))

    by_sub=defaultdict(lambda : [0,0])
    misses=[]
    skipped=0
    for it in data:
        q=it["question"]
        sub=it.get("subtype") or it.get("trap") or "?"
        res=cr.resolve(q)
        if not _is_company_subtype(sub):
            skipped+=1
            continue
        q=it["question"]
        handled=res["status"]!="resolved"
        by_sub[sub][0]+=1
        by_sub[sub][1]+=handled
        if not handled:
            misses.append((it.get("id"),q,res))
    total=sum(v[0] for v in by_sub.values())
    ok=sum(v[1] for v in by_sub.values())
    print(f"\n=== Gate company-resolution: {ok}/{total} handled "
          f"({100*ok/total:.1f}%) ===")
    print(f"(skipped {skipped} year/concept questions — those are the router's job)\n")   
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
        print("\n  PASS: every company-based reject was caught.")
 
if __name__ == "__main__":
    main()