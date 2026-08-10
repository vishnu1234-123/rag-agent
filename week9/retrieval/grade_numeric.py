
"""
Grade the numeric path: retrieval + compute, against the real eval sets.
 
Pipeline per question:  route() + resolve() -> build_query -> numeric_retrieve
                        -> compute() -> compare to eval ground truth.
 
The grader uses `subtype` ONLY to know which expected field to compare against.
It never computes the answer itself — the delta/argmax comes from compute(),
the real runtime layer. That keeps the test honest.
 
Results are PARTITIONED: PASS / FAIL (compute wrong) / BLOCKED (Bucket 2).
 
Run from repo root:  python3 week9/retrieval/grade_numeric.py
"""

import sys,os,json

HERE=os.path.dirname(os.path.abspath(__file__))
ROOT=os.path.abspath(os.path.join(HERE,"..",".."))
sys.path.insert(0,os.path.join(ROOT,"week9","gate"))
sys.path.insert(0,os.path.join(ROOT,"week9","router"))
sys.path.insert(0,HERE)

import company_resolution as cr
from router import route
from numeric_retriever import build_query,numeric_retrieve
from numeric_compute import compute

DB=os.path.join(ROOT,"week8","data","facts.sqlite")
EVAL_DIR=os.path.join(ROOT,"week8","eval")

def close(a,b,rel=1e-6):
    try:
        a,b=float(a),float(b)
    except (TypeError,ValueError):
        return False
    if a==b:
        return True
    return abs(a - b) / max(abs(a), abs(b), 1.0) <= rel

def run_pipeline(q):
    nq=build_query(route(q,use_llm=False),cr.resolve(q),q)
    out=numeric_retrieve(nq,DB)
    return out,compute(out)

def check(item,comp):
    st=comp.get("status")
    if st in ("blocked","rejected") or comp["kind"]=="none":
        rstat=comp.get("retrieval",{}).get("status")
        if rstat=="blocked":
            return "BLOCKED"
        return False
    exp=item["expected_value"]
    if comp["kind"]=="point":
        return close(comp["value"],exp)
    if comp["kind"] in ("delta", "trend"):
        return close(comp["delta"], exp)
    if comp["kind"]=="gap":
        return close(comp["gap"],exp)
    if comp["kind"]=="growth_compare":
        return comp["winner"]==exp
    if comp["kind"] == "ranking":
        return comp["winner_ticker"] == exp
    return False

def grade(path):
    data=json.load(open(path))
    buckets={"PASS":[],"FAIL":[],"BLOCKED":[]}
    for it in data:
        q=it["question"]
        try:
            out,comp=run_pipeline(q)
        except Exception as e:
            buckets["FAIL"].append((it["id"],f"exception: {e}"))
            continue
        res=check(it,comp)
        if res=="BLOCKED":
            buckets["BLOCKED"].append((it["id"],it.get("subtype")))
        elif res:
            buckets["PASS"].append(it["id"])
        else:
            buckets["FAIL"].append((it["id"],
            f"kind={comp.get("kind")} status={comp.get("status")} exp={item_exp(it)}"))
    return buckets,len(data)

def item_exp(it):
    return it["expected_value"]

def report(name,buckets,n):
    print(f"=== {name} ===")
    print(f"PASS {len(buckets['PASS'])}/{n}   FAIL {len(buckets['FAIL'])}   BLOCKED(bucket2) {len(buckets['BLOCKED'])}")

    for fid,why in buckets["FAIL"]:
        print(f" FAIL {fid}: {why}")
    for fid,sub in buckets["BLOCKED"]:
        print(f" BLOCKED {fid} ({sub})")
    print()
if __name__=="__main__":
    b1,n1=grade(os.path.join(EVAL_DIR,"numeric_eval.json"))
    report("numeric_eval.json",b1,n1)
    b2,n2=grade(os.path.join(EVAL_DIR,"cc_numeric.json"))
    report("cc_numeric.json",b2,n2)
    tp=len(b1["PASS"])+len(b2["PASS"])
    tf=len(b1["FAIL"])+len(b2["FAIL"])
    tb=len(b1["BLOCKED"])+len(b2["BLOCKED"])
    print(f"TOTAL  PASS {tp}/{n1+n2}   FAIL {tf}   BLOCKED(bucket2) {tb}")
    print("\nBLOCKED = multi-company / short-ticker resolution, deferred to Bucket 2.")
    print("Meaningful compute score = PASS vs FAIL, excluding BLOCKED.")