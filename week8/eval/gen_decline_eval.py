"""
Honest-decline eval generator for FilingsIQ.
 
This is the differentiator category: a finance tool must DECLINE honestly when
it can't answer, never hallucinate. These questions look answerable but aren't,
and the "correct" behavior is a graceful decline (optionally with a redirect to
what the system DOES cover).
 
Four flavors:
  out_of_corpus   — a real company NOT in the 20-company corpus (Netflix, Intel).
                    Expected: decline, "not in coverage".
  out_of_concept  — a real in-corpus company, but a metric NOT stored
                    (profit margin, EPS, employees, R&D). Expected: decline +
                    redirect to the 3 stored concepts.
  out_of_range    — real company + real concept, but a year outside the data
                    (2015, 2030). Expected: decline, "no data for that year".
  misspelling     — a near-miss of an in-corpus name (aple, Microsft). Expected:
                    decline or "did you mean X?" — NOT a silent wrong-entity answer.
 
Design notes:
  - out_of_corpus / out_of_concept / out_of_range are generated programmatically
    by deliberately choosing companies/concepts/years NOT present in facts.sqlite.
    They are correct-by-construction: the DB is queried to CONFIRM absence.
  - misspelling is a small hand-authored set (typos are not mechanically
    derivable in a way that stays realistic).
  - expected_route = "REJECT" so the same eval also grades the router later.
  - grading is behavioral, not value-based: expected_behavior describes the
    acceptable response; there is no numeric expected_value.
 
Usage:
    python gen_decline_eval.py --db data/facts.sqlite --out decline_eval.json
"""

import argparse
import json
import random
import sqlite3

OUT_OF_CORPUS = [
    ("Netflix", "NFLX"), ("Intel", "INTC"), ("Disney", "DIS"),
    ("PepsiCo", "PEP"), ("Oracle", "ORCL"), ("Pfizer", "PFE"),
    ("Nike", "NKE"), ("McDonald's", "MCD"), ("Salesforce", "CRM"),
    ("Adobe", "ADBE"), ("IBM", "IBM"), ("Cisco", "CSCO"),
    ("Verizon", "VZ"), ("Comcast", "CMCSA"), ("Wells Fargo", "WFC"),
    ("Goldman Sachs", "GS"), ("Costco", "COST"), ("Starbucks", "SBUX"),
]

OUT_OF_CONCEPT_CALC = [
    "profit margin", "gross margin", "operating margin", "net margin",
    "earnings per share", "EPS", "return on equity", "return on assets",
    "dividend yield", "debt-to-equity ratio", "price-to-earnings ratio",
    "market capitalization", "current ratio", "book value per share",
]

OUT_OF_CONCEPT_INPROSE = [
    "number of employees", "total headcount", "number of registered shareholders",
    "number of retail stores", "R&D spending", "advertising spend",
    "operating cash flow", "free cash flow", "capital expenditures",
    "long-term debt",
]

IN_CORPUS_NAMES = {
    "AAPL": "Apple", "AMZN": "Amazon", "BA": "Boeing", "BAC": "Bank of America",
    "BRK-B": "Berkshire Hathaway", "CVX": "Chevron", "GOOGL": "Alphabet",
    "JNJ": "Johnson & Johnson", "JPM": "JPMorgan Chase", "KO": "Coca-Cola",
    "META": "Meta", "MSFT": "Microsoft", "NVDA": "NVIDIA", "PG": "Procter & Gamble",
    "T": "AT&T", "TSLA": "Tesla", "UNH": "UnitedHealth", "V": "Visa",
    "WMT": "Walmart", "XOM": "ExxonMobil",
}

CONCEPT_PHRASE = {
    "revenue": "revenue", "net_income": "net income", "total_assets": "total assets",
}
 
MISSPELLINGS_NEAR = [
    ("aple", "Apple"), ("Microsft", "Microsoft"), ("Amazn", "Amazon"),
    ("Teslla", "Tesla"), ("Wallmart", "Walmart"), ("Nvdia", "NVIDIA"),
    ("JP Morgan Chse", "JPMorgan Chase"),
]
MISSPELLINGS_FAR = [
    ("apppppl", "Apple"), ("Mmmicrsoftt", "Microsoft"), ("Tsltsla", "Tesla"),
    ("Wlllmrt", "Walmart"), ("Nvvvda", "NVIDIA"),
]
NOT_A_COMPANY = [
    "aardvark", "banana", "the weather", "quarterly vibes", "my landlord",
]
 
STORED_CONCEPTS_BLURB = "revenue, net income, or total assets"

def load_db_facts(db_path):
    con=sqlite3.connect(db_path)
    present=set()
    tickers=set()
    concepts=set()
    years=[]

    for t,c,y in con.execute("SELECT ticker,concept,fiscal_year FROM facts"):
        present.add((t,c,y))
        tickers.add(t)
        concepts.add(c)
        years.append(y)
    con.close()
    return present,tickers,concepts,(min(years),max(years))


def gen_out_of_corpus(rng,n):
    out=[]
    picks=rng.sample(OUT_OF_CORPUS,min(n,len(OUT_OF_CORPUS)))
    concepts=["revenue","net_income","total_assets"]
    for name,tk in picks:
        c=rng.choice(concepts)
        y=rng.choice([2023,2024,2025])
        out.append({
            "id":f"decl_corpus_{tk}_{c}_{y}",
            "category":"decline",
            "subtype":"out_of_corpus",
            "expected_route":"REJECT",
            "question": f"What was {name}'s {CONCEPT_PHRASE[c]} in fiscal year {y}?",
            "expected_behavior": (
                f"Decline: {name} is not one of the covered companies. "
                f"Do not produce a number."
            ),
            "trap": f"{name} is not in the 20-company corpus.",
        })
    return out

def gen_out_of_concept(rng,tickers,n_calc,n_inprose):
    out=[]
    tks=list(tickers)
    for _ in range(n_calc):
        tk=rng.choice(tks)
        metric=rng.choice(OUT_OF_CONCEPT_CALC)
        y=rng.choice([2023,2024,2025])
        name=IN_CORPUS_NAMES[tk]
        out.append({
            "id":f"decl_concept_{tk}_{metric.replace(' ','_')}_{y}",
            "category":"decline",
            "subtype":"out_of_concept",
            "severity":"calc",
            "expected_route":"REJECT",
            "question": f"What was {name}'s {metric} in fiscal year {y}?",
            "expected_behavior": (
                f"Decline + redirect: {metric} is a derived metric the system "
                f"does not compute; it covers {STORED_CONCEPTS_BLURB}. "
                f"Do not invent or calculate a figure."
            ),
            "trap": f"{name} is covered, but '{metric}' is a derived/uncovered metric.",
        })
    
    for _ in range(n_inprose):
        tk=rng.choice(tks)
        metric=rng.choice(OUT_OF_CONCEPT_INPROSE)
        y=rng.choice([2023,2024,2025])
        name=IN_CORPUS_NAMES[tk]

        out.append({
            "id": f"decl_concept_inprose_{tk}_{metric.replace(' ', '_')}_{y}",
            "category": "decline",
            "subtype": "out_of_concept",
            "severity": "in_prose",
            "expected_route": "REJECT",
            "question": f"What was {name}'s {metric} in fiscal year {y}?",
            "expected_behavior": (
                f"Decline: {metric} is not a stored concept (system covers "
                f"{STORED_CONCEPTS_BLURB}). NOTE: this figure likely appears in "
                f"{name}'s filing prose, so a system that routes to retrieval "
                f"instead of rejecting will wrongly answer it. Must REJECT before "
                f"retrieval, not answer from a prose chunk."
            ),
            "trap": f"'{metric}' sits verbatim in {name}'s prose — router must "
                    f"reject-first, not retrieve-and-answer.",
        })
    return out
def gen_out_of_range(rng,tickers,year_bounds,n):
    lo,hi=year_bounds
    out_years=[lo -6,lo-3,hi+2,hi+5]
    out=[]
    tks=list(tickers)
    for _ in range(n):
        tk=rng.choice(tks)
        c=rng.choice(["revenue","net_income","total_assets"])
        y=rng.choice(out_years)
        name=IN_CORPUS_NAMES[tk]
        reason= "predates the data" if y < lo else "is in the future / not yet filed"
        out.append({
            "id":f"decl_range_{tk}_{c}_{y}",
            "category":"decline",
            "subtype":"out_of_range",
            "expected_route":"REJECT",
            "question": f"What was {name}'s {CONCEPT_PHRASE[c]} in fiscal year {y}?",
            "expected_behavior": (
                f"Decline: no data for fiscal {y} ({reason}); "
                f"coverage is {lo}-{hi}. Do not extrapolate a number."
            ),
            "trap": f"{name}/{c} is covered, but year {y} is outside {lo}-{hi}.",
        })
    return out

def gen_misspelling(rng,n_near,n_far,n_notco):
    out=[]

    for typo,intended in rng.sample(MISSPELLINGS_NEAR,min(n_near,len(MISSPELLINGS_NEAR))):
        c=rng.choice(["revenue","net_income","total_assets"])
        y=rng.choice([2023,2024,2025])
        out.append({
            "id":f"decl_typonear_{typo.replace(' ','_')}_{c}_{y}",
            "category":"decline",
            "subtype":"misspelling",
            "severity":"near",
            "expected_route":"REJECT",
            "question": f"What was {typo}'s {CONCEPT_PHRASE[c]} in fiscal year {y}?",
            "expected_behavior": (
                f"Recognizable typo of {intended} (edit distance ~1-2). Acceptable: "
                f"resolve to {intended}, or confirm 'did you mean {intended}?'. "
                f"Only clear failure is answering as a DIFFERENT entity or inventing "
                f"a figure without acknowledging the ambiguity."
            ),
            "trap": f"'{typo}' -> {intended}; must not silently wrong-match.",
        })
    
    for typo,intended in rng.sample(MISSPELLINGS_FAR,min(n_far,len(MISSPELLINGS_FAR))):
        c=rng.choice(["revenue","net_income","total_assets"])
        y=rng.choice([2023,2024,2025])
        out.append({
            "id":f"decl_typofar_{typo.replace(' ','_')}_{c}_{y}",
            "category":"decline",
            "subtype":"misspelling",
            "severity":"far",
            "expected_route":"REJECT",
            "question": f"What was {typo}'s {CONCEPT_PHRASE[c]} in fiscal year {y}?",
            "expected_behavior": (
                f"Mangled beyond confident recognition. Should DECLINE / ask the "
                f"user to clarify. Confidently resolving to {intended} (or any "
                f"company) is OVER-EAGER and counts as a failure — this is the "
                f"wrong-entity risk the system must guard against."
            ),
            "trap": f"'{typo}' is too garbled to safely resolve; over-eager match = fail.",
        })
    
    for token in rng.sample(NOT_A_COMPANY,min(n_notco,len(NOT_A_COMPANY))):
        c=rng.choice(["revenue","net_income","total_assets"])
        y=rng.choice([2023,2024,2025])
        out.append({
            "id":f"decl_notco_{token.replace(' ','_')}_{c}_{y}",
            "category":"decline",
            "subtype":"misspelling",
            "severity":"not_a_company",
            "expected_route":"REJECT",
            "question": f"What was {token}'s {CONCEPT_PHRASE[c]} in fiscal year {y}?",
            "expected_behavior": (
                f"'{token}' is not a company. Should DECLINE. Any attempt to map it "
                f"to a real company or produce a figure is a failure."
            ),
            "trap": f"'{token}' is not a company name at all.",
        })
    return out

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--db",default="data/facts.sqlite")
    ap.add_argument("--out",default="decline_eval.json")
    ap.add_argument("--seed",type=int,default=42)
    ap.add_argument("--n-corpus",type=int,default=10)
    ap.add_argument("--n-concept-calc",type=int,default=8)
    ap.add_argument("--n-concept-inprose",type=int,default=8)
    ap.add_argument("--n-range",type=int,default=6)
    ap.add_argument("--n-typo-near",type=int,default=5)
    ap.add_argument("--n-typo-far",type=int,default=4)
    ap.add_argument("--n-notco",type=int,default=3)
    args=ap.parse_args()

    rng=random.Random(args.seed)
    present,tickers,cocnepts,year_bounds=load_db_facts(args.db)

    items=[]
    items+=gen_out_of_corpus(rng,args.n_corpus)
    items+=gen_out_of_concept(rng,tickers,args.n_concept_calc,args.n_concept_inprose)
    items+=gen_out_of_range(rng,tickers,year_bounds,args.n_range)
    items+=gen_misspelling(rng,args.n_typo_near,args.n_typo_far,args.n_notco)

    with open(args.out,"w") as f:
        json.dump(items,f,indent=2)
    
    from collections import defaultdict

    by=defaultdict(int)
    by_sev=defaultdict(int)
    for it in items:
        by[it["subtype"]]+=1
        if it.get("severity"):
            by_sev[it["severity"]]+=1
    print(f"[done] wrote {len(items)} decline questions -> {args.out}")
    for k in ("out_of_corpus","out_of_concept","out_of_range","misspelling"):
        extra=""
        if k=="misspelling":
            extra = (f"  (near {by_sev['near']}, far {by_sev['far']}, "
                     f"not_a_company {by_sev['not_a_company']})")
        print(f"  {k:15} {by[k]}{extra}")
    print("\n--- samples ---")
    
    shown=set()
    for it in items:
        key=it.get("severity") or it["subtype"]
        if key not in shown:
            shown.add(key)
            print(f"\n[{it['subtype']}"
                  + (f" / {it['severity']}" if it.get("severity") else "") + "]")
            print(f"Q: {it['question']}")
            print(f"Expected: {it['expected_behavior']}")

if __name__=="__main__":
    main()
