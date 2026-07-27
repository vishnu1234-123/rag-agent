"""
FilingsIQ - Save resolved filing list to disk (Week 8, Step 4b)

Small addition to lookup_filings.py: instead of just printing results,
save them to a JSON file so the next step (batch fetch + extract + dedup
across all 20 companies) can read from it programmatically, rather than
copy-pasting URLs by hand.

USAGE (from filingsiq/ repo root, AFTER running lookup_filings.py once
to confirm output looks correct):
    python ingestion/save_filing_list.py

OUTPUT:
    data/filing_list.json - list of {ticker, cik, form, accessionNumber,
    primaryDocument, filingDate, reportDate, url} for all resolved filings
"""

import json
from pathlib import Path
from lookup_filings import main as run_lookup

OUTPUT_PATH=Path("data/filing_list.json")

def save():
    results=run_lookup()
    OUTPUT_PATH.parent.mkdir(parents=True,exist_ok=True)
    with open(OUTPUT_PATH,"w") as f:
        json.dump(results,f,indent=2)
        print(f"\n[saved] {len(results)} filings -> {OUTPUT_PATH}")


if __name__ == "__main__":
    save()
