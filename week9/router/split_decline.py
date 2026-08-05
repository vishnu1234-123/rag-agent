"""
Split decline_eval.json into two eval sets by WHO owns the reject:
 
  decline_router.json  — rejects the ROUTER owns (company-independent):
                         impossible/malformed year, unsupported numeric concept.
  decline_gate.json    — rejects the RETRIEVAL GATE owns (company-based):
                         out-of-corpus company, typos, not-a-company.
 
After the router refactor (router classifies TYPE, gate resolves COMPANY), the
company-based rejects are no longer router failures — they route NUMERIC and the
gate rejects them. Splitting the eval makes each component's score honest.
 
Classification is by the question's `subtype`/`trap`/`id` fields. Anything we
can't confidently classify is reported so you can eyeball it, not silently
dropped.
"""

import json,sys,re
import shutil

SRC = "../../week8/eval/decline_eval.json"

GATE_MARKERS=("corpus","typonear","typofar","notco","not_co","outof","out_of")
ROUTER_MARKERS = ("year", "malformed", "absurd", "unparse", "concept", "unsupported", "fcf", "grossmargin", "eps")

def classify(item):
    hay=" ".join(str(item.get(k,"")) for k in ("id","subtype","trap")).lower()
    if any(m in hay for m in GATE_MARKERS):
        return "gate"
    if any(m in hay for m in ROUTER_MARKERS):
        return "router"
    return "unknown"

def main():
    data=json.load(open(SRC))
    router_items,gate_items,unknown=[],[],[]
    for it in data:
        c=classify(it)
        (router_items if c=="router" else gate_items if c=="gate" else "unknown").append(it)
    print(f"total decline: {len(data)}")
    print(f" router-owned (year/concept): {len(router_items)}")
    print(f" gate-owned (company-based): {len(gate_items)}")
    print(f" UNKNOWN (needs eyeball): {len(unknown)}")

    if unknown:
        print("\n--- UNKNOWN, classify these by hand ---")
        for it in unknown:
            print(f" {it.get("id")} :: subtype={it.get("subtype")} trap={it.get("trap")}")
            print(f" {it["question"][:70]}")
    json.dump(router_items,open("../../week8/eval/decline_router.json","w"), indent=2)
    json.dump(gate_items, open("../../week8/eval/decline_gate.json","w"), indent=2)
    print("\nwrote decline_router.json and decline_gate.json")
    print("NOTE: original decline_eval.json is untouched; update test_router.py to "
          "use decline_router.json instead.")
 
if __name__ == "__main__":
    main()
