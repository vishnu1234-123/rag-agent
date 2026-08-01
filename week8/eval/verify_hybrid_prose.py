"""
Interactive verification for cross-company hybrid / cross_prose questions.
 
Walks you through each drafted question one at a time, showing the numeric
answer, both companies' drafted prose, and the source chunk ids. You decide:
 
  k  keep as-is        -> verified=true
  c  cut this question -> dropped from the final set
  f  flag to fix later -> kept, verified stays false, note added
  s  skip (decide later)
  q  quit and save progress
 
Checks to run in your head for each (the helper prints these reminders):
  * Real & grounded?      each reason actually in that company's chunks
  * No cross-attribution? company A's reason is A's, not B's
  * Answers the question?  (e.g. a total-assets question must give ASSET
                            reasons, not income reasons — the known drift)
  * NOT_FOUND?            keyword search missed; verify by hand or cut
 
misleading_comparison items have no prose to verify — the helper auto-keeps
them (numeric is exact, caveat is curated) but shows them so you can eyeball
the numbers.
 
Writes the surviving verified questions to --out. Safe to quit and resume:
re-running skips items already decided (verified=true or cut-logged).
 
Usage:
    python verify_hybrid_prose.py --in cc_hybrid_drafted.json --out cc_hybrid_final.json
"""

import argparse
import json
import sys
from pathlib import Path

def show(it,i,n):
    print("\n" + "=" * 74)
    print(f"[{i}/{n}]  {it['subtype']}   route={it['expected_route']}   id={it['id']}")
    print("-" * 74)
    print("Q:",it["question"])
    if it.get("expected_answer_numeric"):
        print("\nNUMERIC (exact):",it["expected_answer_numeric"])
    if it["subtype"]=="misleading_comparison":
        print("\nEXPECTED BEHAVIOR:",it.get('expected_behavior')[:300])
        print("\n(misleading item - no prose to verify; check the numbers read right)")
        return
    dp=it.get("drafted_prose",{})
    if not dp:
        print("\n(!) no drafted_prose on this item")
    
    concept_assets="total_assets" in it["question"].lower()
    print("\nCHECK: real&grounded? · no cross-attribution? · answers the question?"
          + ("  [ASSETS q — reasons must be about ASSET growth, not income!]"
             if concept_assets else ""))
    
    for tk,d in dp.items():
        print(f"\n  --- {d.get('company', tk)} ---")
        ans = d.get("answer", "")
        flag = "  <<< NOT_FOUND — verify by hand or cut" if ans.strip() == "NOT_FOUND" else ""
        print(f"  {ans}{flag}")
        print(f"  [chunks: {d.get('source_chunk_ids', [])}]")

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--in",dest="inp",default="cc_hybrid_drfated.json")
    ap.add_argument("--out",default="cc_hybrid_final.json")
    args=ap.parse_args()

    items=json.load(open(args.inp))
    n=len(items)

    decided={}

    if Path(args.out).exists():
        for it in json.load(open(args.out)):
            decided[it["id"]]=it
    kept,cut,flagged=[],[],[]
    print(f"Verifying {n} cross-company questions. Commands: k keep · c cut · "
          f"f flag-fix · s skip · q quit-save\n")
    
    for i,it in enumerate(items,1):
        if it["subtype"]=="misleading_comparision":
            show(it,i,n)
            it["verified"]=True
            kept.append(it)
            print(" -> auto-kept (misleading; numeric exact)")
            continue

        if it["id"] in decided and decided[it["id"]].get("verified"):
            kept.append(decided[it["id"]])
            print(f"[{i}/{n}] {it['id']} already verified - skipping")
            continue

        show(it,i,n)
        while True:
            choice=input("\n [k/c/f/s/q] >").strip().lower()
            if choice in ("k","c","f","s","q"):
                break
            print(" enter k,c,f,s or q")
        
        if choice=="q":
            print(" quitting, saving progress...")
            break
        elif choice=="k":
            it["verified"]=True
            kept.append(it)
        elif choice=="c":
            cut.append(it["id"])
        elif choice=="f":
            note=input(" fix note> ").strip()
            it["verified"]=False
            it["fix_note"]=note
            flagged.append(it)
            kept.append(it)
        elif choice=="s":
            kept.append(it)
    
    json.dump(kept,open(args.out,"w"),indent=2)
    print("\n" + "=" * 74)
    print(f"SAVED -> {args.out}")
    print(f"  kept/verified: {sum(1 for it in kept if it.get('verified'))}")
    print(f"  flagged-to-fix: {len(flagged)}")
    print(f"  cut: {len(cut)}  {cut if cut else ''}")
    print(f"  total in final file: {len(kept)}")
    if flagged:
        print("\n  flagged for fixing:")
        for it in flagged:
            print(f"    [{it['id']}] {it.get('fix_note','')}")
 
 
if __name__ == "__main__":
    main()
