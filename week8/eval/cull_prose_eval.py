"""
Cull reviewed prose questions and lock the verified set.
 
After a human read-through, this drops the flagged questions (by their 1-based
position in the current prose_eval.json) and marks every survivor verified=true.
It also strips the bulky source_text field from the final set (kept during
generation for review; not needed once verified).
 
Backs up the input first, so a mistake is always recoverable.
 
Usage:
    # from week8/eval, with prose_eval.json present:
    python cull_prose_eval.py --drop 4,13,15,18,32,57
    python cull_prose_eval.py --drop 4,13,15,18,32,57 --keep-source-text
"""

import argparse
import json
import shutil
from pathlib import Path
from collections import defaultdict

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--in",dest="inp",default="prose_eval.json")
    ap.add_argument("--out",default="prose_eval.json")
    ap.add_argument("--drop",default="",help="comma-separated 1-based indices to remove, e.g. 4,13,15")
    ap.add_argument("--keep-source-text",action="store_true",
                    help="keep the source_text field (default: strip it)")
    args=ap.parse_args()

    inp=Path(args.inp)
    items=json.load(open(inp))
    n=len(items)

    drop=set()

    if args.drop.strip():
        for tok in args.drop.split(","):
            tok=tok.strip()
            if tok:
                idx=int(tok)
                if 1<=idx<=n:
                    drop.add(idx)
                else:
                    print(f" [warn] index {idx} out of range 1..{n}, ignorning")
                
    backup=inp.with_suffix(inp.suffix+".bak")
    shutil.copy(inp,backup)
    print(f"[backup] {inp} -> {backup}")

    kept=[]
    dropped=[]

    for i,it in enumerate(items,1):
        if i in drop:
            dropped.append((i,it.get("ticker"),it.get("question","")[:60]))
            continue
        it["verified"]=True
        if not args.keep_source_text:
            it.pop("source_text",None)
        kept.append(it)

    json.dump(kept,open(args.out,"w"),indent=2)

    print(f"\n [cull] {n} in -> {len(kept)} kept, {len(dropped)} dropped")

    if dropped:
        print(" dropped:")
        for i,tk,q in dropped:
            print(f"    #{i:2} [{tk}] {q}")
    
    by_route=defaultdict(int)
    by_co=defaultdict(int)
    for it in kept:
        by_route[it.get("expected_route","?")]+=1
        by_co[it.get("ticker","?")]+=1
    
    print(f"\n locked set: {len(kept)} verified prose questions")
    print(f" routes: "+", " .join(f"{r}={k}" for r,k in sorted(by_route.items())))
    print(f" companies: {len(by_co)} of 20")
    src_note="kept" if args.keep_source_text else "stripped"
    print(f" source_text: {src_note}")
    print(f"\n written -> {args.out} (original backed up at {backup})")

if __name__=="__main__":
    main()

