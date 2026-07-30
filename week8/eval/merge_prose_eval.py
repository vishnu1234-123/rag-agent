"""
Merge the prose eval batches into one deduplicated set.
 
Combines prose_eval.json + prose_eval_b.json + prose_eval_c.json (or any files
you pass), then:
  - dedups by source_chunk_id (different seeds can hit the same chunk)
  - dedups by near-identical question text (belt and suspenders)
  - re-applies the numeric-lookup filter (catches any straggler that predates
    the current filter, and is a no-op for clean items)
  - renumbers nothing (ids stay stable, tied to source chunk)
  - writes the merged set and prints a summary + section/route breakdown
 
Writes to prose_eval_merged.json by default so it never clobbers an input.
Review it, and when happy, rename it to prose_eval.json.
 
Usage:
    python merge_prose_eval.py                       # uses the 3 default batches
    python merge_prose_eval.py a.json b.json c.json  # explicit inputs
    python merge_prose_eval.py --out final.json
"""

import argparse
import json
import re
import sys
from collections import defaultdict
from pathlib import Path

DEFAULT_INPUTS = ["prose_eval.json", "prose_eval_b.json", "prose_eval_c.json"]

def is_numeric_lookup(question,answer):
    pass

def norm_q(q):
    pass

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("inputs",nargs="*",default=DEFAULT_INPUTS)
    ap.add_argument("--out",default="prose_eval_merged.json")
    ap.add_argument("--dir",default=".",help="folder holding the input files")
    args=ap.parse_args()

    base=Path(args.dir)
    inputs=args.inputs or DEFAULT_INPUTS
    combined=[]

    for name in inputs:
        p=base/name
        if not p.exists():
            print(f" [warn] missing, skipping: {p}")
            continue
        batch=json.load(open(p))
        combined.append((name,batch))
        print(f"[load] {name}: {len(batch)} questions")
    
    if not combined:
        print("ERROR: no input files found",file=sys.stderr)
        sys.exit(1)
    
    seen_cids=set()
    seen_qs=set()
    kept=[]
    dup_cid=dup_q=numeric=0

    for name,batch in combined:
        for it in batch:
            cid=it.get("source_chunk_id")
            if cid and cid in seen_cids:
                dup_cid+=1
                continue
            qn=norm_q(it.get("question")) 
            if qn and qn in seen_qs:
                dup_q+=1
                continue
            if is_numeric_lookup(it.get("question"),it.get("reference_answer")):
                numeric+=1
                continue
            if cid:
                seen_cids.add(cid) 
            if qn:
                seen_qs.add(qn)
            kept.append(it)
    out_path=base/args.out
    json.dump(kept,open(out_path,"w"),indent=2)

    total_in=sum(len(b) for _,b in combined)
    print(f"\n[merge] {total_in} in -> {len(kept)} kept")
    print(f"        dropped: {dup_cid} dup chunk, {dup_q} dup question, "
          f"{numeric} numeric-lookup")
    print(f"        -> {out_path}")

    by_route=defaultdict(int)
    by_company=defaultdict(int)

    for it in kept:
        by_route[it.get("expected_route","?")]+=1
        by_company[it.get("ticker","?")]+=1

    print("\n by route:")

    for r,k in sorted(by_route.items()):
        print(f" {r:12} {k}")
    print("\n companies represented:",len(by_company),"of 20")
    thin=[t for t in by_company if by_company[t]==0]
    missing = set([
        "AAPL","AMZN","BA","BAC","BRK-B","CVX","GOOGL","JNJ","JPM","KO",
        "META","MSFT","NVDA","PG","T","TSLA","UNH","V","WMT","XOM",
    ]) - set(by_company)

    if missing:
        print("NOT represented:",",".join(sorted(missing)))
    
    print(f"\n NEXT : review {args.out}, then rename to prose_eval.json when happy.")


if __name__=="__main__":
    main()


