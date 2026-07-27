"""
FilingsIQ - Survey section-boundary patterns across all 20 companies
(Week 8, Step 10 - chunking prep)

Before committing to ANY chunking boundary rule, survey how section
headers actually appear across all 40 filings. We already know Apple uses
plain 'Item 1A. Risk Factors' lines - but filings vary (banks, foreign
structure, Docling per-filer quirks), so verify before hardening a rule.

For each filing this reports:
  - how many candidate section-header lines match each pattern variant
  - a sample of the actual matched lines (so we see real formatting)
  - whether the standard 10-K items (1, 1A, 7, 7A, 8) are each detectable

Goal: find the boundary detection that works ACROSS all 20, or discover
that we need per-form (10-K vs 10-Q) or per-filer handling.

USAGE (from repo root):
    python ingestion/survey_sections.py
"""

import re
import json
from pathlib import Path
from collections import defaultdict

PROCESSED_DIR=Path("data/processed")
FILING_LIST_PATH=Path("data/filing_list.json")

PATTERNS = {
    "Item N. plain":    re.compile(r"(?im)^item\s+\d+[a-z]?\.\s+\S"),      # "Item 1A. Risk Factors"
    "ITEM N CAPS":      re.compile(r"(?m)^ITEM\s+\d+[A-Z]?\b"),            # "ITEM 1A"
    "Part N":           re.compile(r"(?im)^part\s+[iv]+\b"),               # "Part I", "Part II"
    "toc link (skip)":  re.compile(r"\[Item\s+\d+[a-z]?\.\]\(#"),          # ToC link form - must EXCLUDE
}

KEY_ITEMS = ["1", "1A", "7", "7A", "8"]

def is_toc_line(line: str) -> bool:
    return "](#" in line or ("|" in line and "item" in line.lower())

def survey_file(ticker,form_tag):
    path=PROCESSED_DIR/ticker/f"{ticker}_{form_tag}_full.md"
    if not path.exists():
        return None
    text=path.read_text()
    lines=text.splitlines()

    counts=defaultdict(int)
    samples=defaultdict(list)

    for line in lines:
        stripped=line.strip()
        for name,pat in PATTERNS.items():
            if pat.search(stripped):
                if name!="toc link (skip)" and is_toc_line(stripped):
                    continue
                counts[name]+=1
                if len(samples[name])<2:
                    samples[name].append(stripped[:70])
    
    key_found=[]
    if form_tag=="10K":
        for item in KEY_ITEMS:
            pat = re.compile(rf"(?im)^item\s+{re.escape(item)}\.\s+\S")
            found = any(pat.search(l.strip()) and not is_toc_line(l) for l in lines)
            key_found.append(item if found else f"~{item}")

    return {"counts":dict(counts),"samples":dict(samples),"key_items":key_found}

def main():
    with open(FILING_LIST_PATH) as f:
        filings=json.load(f)
    tickers=list(dict.fromkeys(fl["ticker"] for fl in filings))

    for ticker in tickers:
        for form_tag in ["10K","10Q"]:
            r=survey_file(ticker,form_tag)
            if r is None:
                continue
            c=r["counts"]
            summary=" | ".join(f"{k}:{v}" for k, v in c.items() if v)
            print(f"{ticker:<7}{form_tag:<5}{summary}")
            if form_tag=="10K":
                print(f"         key items detectable: {r['key_items']}")
            for name in ["Item N. plain", "ITEM N CAPS", "Part N"]:
                if r["samples"].get(name):
                    print(f"         [{name}] e.g. {r['samples'][name][0]!r}")
                    break
        print()


if __name__ == "__main__":
    main()
