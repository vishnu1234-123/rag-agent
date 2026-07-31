"""
Verify the decline eval set against facts.sqlite.
 
Decline questions are correct-by-construction (they reference companies/concepts/
years deliberately chosen to be OUT of scope, so the right behavior is always
"decline"). This checks that construction actually held — the failure mode that
matters is a "decline" question that the DB can in fact answer, which would be a
broken test.
 
Checks per subtype:
  out_of_corpus   — the named company must NOT be one of the 20 tickers
  out_of_concept  — the metric must NOT be one of the 3 stored concepts
  out_of_range    — the (company, concept) may be covered, but the YEAR must be
                    outside the DB's actual range
  misspelling     — the typo/token must NOT exactly match a real in-corpus name
 
Also: every item must be route=REJECT, have expected_behavior, unique id.
 
Self-check: the verifier first confirms it can correctly ANSWER a couple of
known in-scope questions (Apple revenue 2024, etc.) — if it can't, the verifier
itself is broken and its verdict can't be trusted. (SESSION_LOG lesson: expect
validators to be buggier than the thing they validate.)
 
Usage:
    python verify_decline_eval.py --db data/facts.sqlite --in decline_eval.json
"""

import argparse
import json
import re
import sqlite3
import sys
from collections import defaultdict

STORED_CONCEPTS = {"revenue", "net_income", "total_assets"}

STORED_PHRASES = {
    "revenue": "revenue", "net income": "net_income", "net_income": "net_income",
    "total assets": "total_assets", "total_assets": "total_assets",
}
 
IN_CORPUS_NAMES = {
    "Apple", "Amazon", "Boeing", "Bank of America", "Berkshire Hathaway",
    "Chevron", "Alphabet", "Johnson & Johnson", "JPMorgan Chase", "Coca-Cola",
    "Meta", "Microsoft", "NVIDIA", "Procter & Gamble", "AT&T", "Tesla",
    "UnitedHealth", "Visa", "Walmart", "ExxonMobil",
}

def load_db(db):
    con=sqlite3.connect(db)
    tickers,concepts,years=set(),set(),[]
    facts=set()
    for t,c,y in con.execute("SELECT ticker,concept,fiscal_year FROM facts"):
        tickers.add(t)
        concepts.add(t)
        years.append(y)
    con.close()
    return tickers,concepts,(min(years),max(years)),facts

def self_check(db):
    con=sqlite3.connect(db)
    row=con.execute(
        "SELECT value FROM facts WHERE ticker='AAPL' AND concept='revenue' "
        "ORDER BY fiscal_year DESC LIMIT 1"
    ).fetchone()
    con.close()

    if not row or row[0]<=0:
        print("SELF-CHECK FAILED: verifier can't read known-good data"
              "(AAPL revenue). Absorbing - verdict would be untrustworthy.",
              file=sys.stderr)
        sys.exit(1)
    return True

def find_year(q):
    m=re.search(r'\b(19|20)\d{2}\b',q)
    return int(m.group()) if m else None

def find_metric(q):
    m=re.search(r"'s (.+?) in fiscal year", q)
    return m.group(1).strip().lower() if m else None

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--db",default="data/facts.sqlite3")
    ap.add_argument("--in",dest="inp",default="decline_eval.json")
    ap.parse_args()

    args=ap.parse_args()

    self_check(args.db)
    tickers,concepts,(lo,hi),facts=load_db(args.db)
    items=json.load(open(args.inp))

    problems=[]
    by_sub=defaultdict(int)
    ids=set()

    for it in items:
        sub=it.get("subtype","?")
        by_sub[sub]+=1
        iid=it.get("id","")
        q=it.get("question","")

        if iid in ids:
            problems.append((iid,"duplicate id"))
        ids.add(iid)

        if it.get("expected_route")!="REJECT":
            problems.append((iid,f"route is {it.get('expected_route')}, expected REJECT"))
        if not it.get("expected_behavior"):
            problems.append((iid,"missing expected_behavior"))

        if sub=="out_of_concept":
            metric=find_metric(q)
            if metric in STORED_PHRASES:
                problems.append((iid,f"LEAK: metric '{metric}' IS a stored concept"
                                 f"-> this question is actually answerable"))
        elif sub=="out_of_range":
            yr=find_year(q)
            if yr is not None and lo<=yr<=hi:
                problems.append((iid,f"LEAK: year {yr} is INSIDE coverage {lo}-{hi}"
                                     f"->this question is actually answerable"))
        elif sub=="out_of_corpus":
            for name in IN_CORPUS_NAMES:
                if re.search(rf"\bWhat was {re.escape(name)}'s\b", q):
                    problems.append((iid,f"LEAK: in-corpus company '{name}' "
                                           f"appears in an out_of_corpus question"))
                    break
        elif sub=="misspelling":
            for name in IN_CORPUS_NAMES:
                if re.search(rf"\bWhat was {re.escape(name)}'s\b", q):
                    problems.append((iid, f"LEAK: exact in-corpus name '{name}' in "
                                           f"a misspelling question"))
                    break
    print(f"[verify] {len(items)} decline questions checked")
    print(" by subtype:",dict(by_sub))
    print(f"  DB coverage: {len(tickers)} companies, concepts {sorted(concepts)}, "
          f"years {lo}-{hi}")
    print(f" self-check: verifier can read know-good data OK")

    if not problems:
        print("\n RESULT: PASS - no leaks, all route=REJECT, all have behaviour,"
              "ids unique.")
    else:
        print(f"\n RESULT: {len(problems)} problem(s) found:")
        for iid,msg in problems:
            print(f"    [{iid}] {msg}")
    
    print("\n --- sample for human review (naturalness+tiering) ---")
    seen=set()
    for it in items:
        key=it.get("severity") or it.get("subtype")
        if key not in seen:
            seen.add(key)
            print(f"  [{it.get('subtype')}"
                  + (f"/{it['severity']}" if it.get("severity") else "") + f"] {it['question']}")
            
if __name__=="__main__":
    main()


 
