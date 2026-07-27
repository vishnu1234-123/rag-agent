"""
Show ONLY the 10-K filings where the plain 'Item N.' rule missed a key
section, plus what the actual header line looks like for the missed item.
Short output - just the problem cases - so we can see real deviations.

USAGE (from repo root):
    python ingestion/show_deviations.py
"""

import re
import json
from pathlib import Path

PROCESSED_DIR = Path("data/processed")
KEY_ITEMS = ["1", "1A", "1B", "2", "3", "5", "7", "7A", "8", "9A"]


def is_toc(line):
    return "](#" in line or ("|" in line and "item" in line.lower())

def check(ticker):
    path=PROCESSED_DIR/ticker/f"{ticker}_10K_full.md"
    if not path.exists():
        return
    lines=path.read_text().splitlines()
    missed=[]
    for item in KEY_ITEMS:
        pat=re.compile(rf"(?im)^item\s+{re.escape(item)}\.\s+\S")
        if not any(pat.search(l.strip()) and not is_toc(l) for l in lines):
            missed.append(item)
    
    if missed:
        print(f"\n{ticker} 10-K missed: {missed}")
        for item in missed:
            loose = re.compile(rf"(?i)item\s+{re.escape(item)}\b")
            hits = [l.strip()[:90] for l in lines if loose.search(l) and not is_toc(l)]
            print(f"   Item {item}: " + (repr(hits[0]) if hits else "NO mention at all outside ToC"))

def main():
    with open("data/filing_list.json") as f:
        tickers=list(dict.fromkeys(fl["ticker"] for fl in json.load(f)))
    print("10-K filings where plain 'Item N.' rule missed a key section:")
    for t in tickers:
        check(t)
    print("\n(done - companies not listed had all key items cleanly detected)")


if __name__ == "__main__":
    main()
