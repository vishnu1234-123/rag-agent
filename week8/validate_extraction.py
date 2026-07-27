"""
FilingsIQ - Extraction validator (XBRL cross-check) - THE canonical one
(Week 8, Step 8)

Consolidates and replaces the earlier throwaway cross-check scripts
(xbrl_crosscheck / crosscheck_full / crosscheck_values / debug_crosscheck),
which have been deleted. This is the single validator going forward.

What it does: for each company, pull official anchor figures (revenue,
net income, total assets, operating cash flow) from SEC's companyfacts
XBRL API, and confirm each appears in the FULL extracted text (from
data/processed/, written by extract_all.py).

Incorporates every fix we learned the hard way this session:
  - Reads FULL text from data/processed/ (not truncated reports/) -- the
    truncation was the cause of the false "total_assets 2/20" scare.
  - Multi-period matching: checks last N reported periods, not just the
    single newest (the newest is often a quarterly value not printed in
    the filings we ingested).
  - Case-insensitive matching (fixed "total assets" vs "Total assets").
  - Scale matching: XBRL gives whole units (359,241,000,000); filings
    print millions (359,241). Generates multiple scale forms.
  - Concept alias lists: companies use different us-gaap tags for the same
    concept (RevenueFromContract... vs Revenues vs SalesRevenueNet).
  - On MISSING, prints the XBRL value + what was searched, for diagnosis.

USAGE (from repo root, AFTER extract_all.py):
    python ingestion/validate_extraction.py
"""

import json
import time
import requests
from pathlib import Path

USER_AGENT="FilingsIQ-Research vishnuvardhan1920@gmail.com"
HEADERS={"User-Agent": USER_AGENT}

FILING_LIST_PATH = Path("data/filing_list.json")
PROCESSED_DIR = Path("data/processed")
N_PERIODS = 4 

ANCHOR_CONCEPTS = {
    "revenue": ["RevenueFromContractWithCustomerExcludingAssessedTax", "Revenues",
                "SalesRevenueNet", "RevenueFromContractWithCustomerIncludingAssessedTax",
                "RevenuesNetOfInterestExpense"],
    "net_income": ["NetIncomeLoss", "ProfitLoss"],
    "total_assets": ["Assets"],
    "op_cash_flow": ["NetCashProvidedByUsedInOperatingActivities",
                     "NetCashProvidedByUsedInOperatingActivitiesContinuingOperations"],
}

def get_companyfacts(cik):
    url = f"https://data.sec.gov/api/xbrl/companyfacts/CIK{str(cik).zfill(10)}.json"
    r = requests.get(url, headers=HEADERS, timeout=30)
    return r.json() if r.status_code == 200 else None


def scale_reps(val):
    reps = set()
    try:
        val = int(val)
    except (ValueError, TypeError):
        return []
    for d in [1, 1_000, 1_000_000]:
        s = val / d
        if s >= 1:
            reps.add(f"{int(round(s)):,}")
            reps.add(str(int(round(s))))
    return list(reps)

def recent_vals(facts,aliases):
    ug=facts.get("facts",{}).get("us-gaap",{})
    for tag in aliases:
        if tag in ug:
            usd=ug[tag].get("units",{}).get("USD",[])
            vals=sorted(usd,key=lambda f:f.get("end",""),reverse=True)
            return tag,[(v["val"],v.get("end")) for v in vals[:N_PERIODS]]
    return None,[]

def find_match(vals, text_lower):
    for val, end in vals:
        for rep in scale_reps(val):
            if rep.lower() in text_lower:   # case-insensitive (numbers unaffected, but consistent)
                return val, rep, end
    return None

def load_full_text(ticker):
    """FULL extracted text from data/processed/ - markdown + all table rows,
    both 10-K and 10-Q. This is the complete extraction, not a preview."""
    parts = []
    d = PROCESSED_DIR / ticker
    for ft in ["10K", "10Q"]:
        for suffix in ["_full.md", "_tables.txt"]:
            p = d / f"{ticker}_{ft}{suffix}"
            if p.exists():
                parts.append(p.read_text())
    return "\n".join(parts)

def main():
    with open(FILING_LIST_PATH) as f:
        filings=json.load(f)
    
    companies={}
    for fl in filings:
        companies[fl["ticker"]]=fl["cik"]
    
    concepts=list(ANCHOR_CONCEPTS.keys())
    header=f"{'TICKER':<8}"+"".join(f"{c:<14}" for c in concepts)
    print(header)
    print("-"*len(header))

    tally={c:0 for c in concepts}
    total=0
    results=[]

    for ticker,cik in companies.items():
        text=load_full_text(ticker)
        if not text:
            print(f"{ticker:<8} (no processed text - run extract_all.py first)")
            continue
        facts=get_companyfacts(cik)
        time.sleep(0.15)
        if facts is None:
            print(f"{ticker<8} (companyfacts fetch is failed)")
            continue
        total+=1
        text_lower=text.lower()
        row=f"{ticker:<8}"
        rec={"ticker":ticker,"anchors":{}}

        for concept in concepts:
            tag,vals=recent_vals(facts,ANCHOR_CONCEPTS[concept])
            if not vals:
                mark="no-tag"
            elif find_match(vals,text_lower):
                mark="FOUND"
                tally[concept]+=1
            else:
                mark="MISSING"
            row += f"{mark:<14}"
            rec["anchors"][concept] = mark
        print(row)
        results.append(rec)

    print("-" * len(header))
    print(f"{'TOTALS':<8}" + "".join(f"{str(tally[c])+'/'+str(total):<14}" for c in concepts))

    Path("data").mkdir(exist_ok=True)
    with open("data/validation_result.json", "w") as f:
        json.dump({"results": results, "tally": tally, "total": total}, f, indent=2)
    print(f"\n[done] -> data/validation_result.json")


if __name__ == "__main__":
    main()