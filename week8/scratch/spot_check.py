"""
FilingsIQ - Manual completeness spot-check of processed markdown
(Week 8, Step 9)

The XBRL validator confirmed the NUMBERS survived extraction. This checks
the OTHER half - that the full document structure is present (narrative
sections + headers + tables), since that's what chunking will consume.

Checks all 20 companies, both 10-K and 10-Q, and prints a structured
fingerprint of each: length, header count (chunker split points), table-row
count, and (for 10-Ks) whether key narrative sections are present. Flags
anything suspicious (tiny file, no headers, missing narrative).

This is a COMPLETENESS check, not a correctness check - confirming the
document is fully there, in structured form, ready to chunk.

USAGE (from repo root):
    python ingestion/spot_check.py
"""

import json
import re
from pathlib import Path 

PROCESSED_DIR = Path("data/processed")
FILING_LIST_PATH = Path("data/filing_list.json")

# narrative sections a real 10-K must have (loose regex, case-insensitive).
# 10-Qs have a different, lighter structure (no Item 1A/1 Business), so we
# only assert these for 10-K.
NARRATIVE_MARKERS = {
    "Item 1A Risk": r"item\s*1a",
    "Item 7 MD&A": r"item\s*7[^0-9aA]",
    "Item 8 Fin.Stmts": r"item\s*8",
}

def fingerprint(ticker,form_tag):
    path=PROCESSED_DIR/ticker/f"{ticker}_{form_tag}_full.md"
    if not path.exists():
        print(f" {ticker:<7} {form_tag:<5} FILE MISSING")
        return None
    
    text=path.read_text()
    lower=text.lower()

    n_chars=len(text)
    n_headers=len(re.findall(r"^#{1,6}\s",text,re.MULTILINE))
    n_table_rows=len(re.findall(r"^\s*\|.*\|\s*$", text, re.MULTILINE))

    if form_tag=="10K":
        missing=[label for label,pat in NARRATIVE_MARKERS.items() if not re.search(pat,lower)]
        narrative="all OK" if not missing else f"MISSING: {missing}"

    else:
        narrative="(n/a for 10-Q)"
    
    suspicious=n_chars<20_000 or n_headers==0 or(form_tag=="10K" and "MISSING" in narrative)
    flag="!!" if suspicious else " "

    print(f"  {flag} {ticker:<7} {form_tag:<5} {n_chars:>9,} chars | {n_headers:>4} hdrs | {n_table_rows:>5} tbl-rows | {narrative}")
    return suspicious

def main():
    with open(FILING_LIST_PATH) as f:
        filings=json.load(f)
    tickers=list(dict.fromkeys(fl["ticker"] for fl in filings))
    print(f"Completeness spot-check: all {len(tickers)} companies, 10-K + 10-Q\n")
    print("  (!! = suspicious: <20k chars, no headers, or missing 10-K narrative section)\n")

    suspicious_count=0
    for ticker in tickers:
        for form_tag in ["10K","10Q"]:
            result=fingerprint(ticker,form_tag)
            if result:
                suspicious_count+=1
        print()
    
    print("-"*70)

    if suspicious_count:
        print(f"{suspicious_count} filing(s) flagged !! - inspect these before chunking.")
    else:
        print("No filings flagged. All extractions look structurally complete.")


if __name__ == "__main__":
    main()

