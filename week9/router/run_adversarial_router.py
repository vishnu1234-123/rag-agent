"""
Run the adversarial router eval in BOTH modes and compare.
 
Usage (from the router dir so `import router` works):
    cd ~/Desktop/"RAG AGENT"/week9/router
    cp /path/to/adversarial_router.json .
    cp /path/to/run_adversarial_router.py .
    python run_adversarial_router.py adversarial_router.json
 
Needs OPENAI_API_KEY for the LLM-on pass. Rules-only pass needs nothing.
"""

import json
import os
import sys

from router import route

def severity(expected,got):

    if expected==got:
        return None
    
    if expected=="REJECT" and got in ("NUMERIC","HYBRID","CONCEPTUAL"):
        return "CRITICAL: answered a should-decline"
    if got=="REJECT" and expected in ("NUMERIC","CONCEPTUAL","HYBRID"):
        return "HIGH: rejected an answerable question"
    return "MED: misroute (%s->%s)" % (expected,got)

def run_mode(items,use_llm,client):
    rows=[]
    for it in items:
        r=route(it["question"],client=client,use_llm=use_llm)
        got=r.get("route")
        exp=it["expected_route"]
        sev=severity(exp,got)

        got_concept=(r.get("numeric_part") or {}).get("concept")
        concept_ok = (it.get("expected_concept") is None) or (got_concept == it["expected_concept"]) or (got == "REJECT" and exp == "REJECT")
        rows.append({
            "id": it["id"], "cat": it["category"], "exp": exp, "got": got,
            "tier": r.get("tier"), "sev": sev,
            "exp_concept": it.get("expected_concept"), "got_concept": got_concept,
            "concept_ok": concept_ok,
        })
    return rows

def summarize(name, rows):
    n = len(rows)
    correct = sum(1 for x in rows if x["sev"] is None)
    print("\n" + "=" * 64)
    print("%s : %d/%d routes correct" % (name, correct, n))
    print("=" * 64)
    # severity tally
    from collections import Counter
    sev = Counter()
    for x in rows:
        if x["sev"]:
            sev[x["sev"].split(":")[0]] += 1
    if sev:
        print("failures by severity:", dict(sev))
    # per-category
    cats = {}
    for x in rows:
        cats.setdefault(x["cat"], [0, 0])
        cats[x["cat"]][1] += 1
        if x["sev"] is None:
            cats[x["cat"]][0] += 1
    print("per-category (correct/total):")
    for c, (ok, tot) in sorted(cats.items()):
        print("   %-24s %d/%d" % (c, ok, tot))
    # list the misses
    print("misses:")
    for x in rows:
        if x["sev"]:
            print("   [%s] %s  exp=%s got=%s tier=%s  %s"
                  % (x["cat"], x["id"], x["exp"], x["got"], x["tier"], x["sev"]))
    # concept extraction misses (separate from routing)
    cmiss = [x for x in rows if not x["concept_ok"]]
    if cmiss:
        print("concept-extraction misses (regex synonym gap):")
        for x in cmiss:
            print("   %s  exp_concept=%s got_concept=%s (route %s)"
                  % (x["id"], x["exp_concept"], x["got_concept"], x["got"]))
    return correct, n

def main():
    path=sys.argv[1] if len(sys.argv)>1 else "adversarial_router.json"
    items=json.load(open(path))
    print("loaded %d adversarial questions"%len(items))

    rules_rows=run_mode(items,use_llm=False,client=None)
    r_ok,r_n=summarize("RULES-ONLY (regex, no LLM)",rules_rows)

    client=None
    if os.getenv("OPENAI_API_KEY"):
        try:
            from openai import OpenAI
            client=OpenAI()
        except Exception as e:
            print("\n(could not init OpenAI client: %s)" % e)
    if client is None:
        print("\n!! OPENAI_API_KEY not set - skipping LLM-on pass.")
        print(" Set it and re-run to get the comparision.")
        return 
    
    llm_rows=run_mode(items,use_llm=True,client=client)
    l_ok,l_n=summarize("LLM-ON (full router)",llm_rows)

    print("\n"+"="*64)
    print("COMPARISION: rules-only %d/%d -> LLM-on %d/%d" % (r_ok,r_n,l_ok,l_n))
    print("="*64)
    by_id={x["id"]:x for x in rules_rows}
    rescued,broke=[],[]
    for x in llm_rows:
        was = by_id[x["id"]]
        if was["sev"] and not x["sev"]:
            rescued.append(x["id"])
        if x["sev"] and not was["sev"]:
            broke.append(x["id"])
    print("LLM rescued (regex wrong -> LLM right):", rescued or "none")
    print("LLM broke   (regex right -> LLM wrong):", broke or "none")
    print("\nRead: 'rescued' = the value of the LLM tier. 'broke' = LLM tier"
          " overriding a correct regex call. CRITICAL/HIGH misses that survive"
          " BOTH passes are the ones to fix first.")
 
 
if __name__ == "__main__":
    main()
    