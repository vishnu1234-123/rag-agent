"""
Verify section_splitter against all 20 real 10-K filings before we build
the chunker on it. For each: how many sections, which items detected, and
CRITICALLY whether no-content-loss holds on real data (not just synthetic).

USAGE (from repo root):
    python ingestion/verify_splitter.py
"""

import json
from pathlib import Path
from section_splitter import split_into_sections,verify_no_loss

PROCESSED_DIR=Path("data/processed")

def main():
    with open("data/filing_list.json") as f:
        tickers=list(dict.fromkeys(fl["ticker"] for fl in json.load(f)))
    
    print(f"{'TICKER':<7}{'SECTIONS':<9}{'ITEMS DETECTED':<40}{'NO-LOSS':<8}")
    print("-"*75)

    any_loss=False

    for ticker in tickers:
        path=PROCESSED_DIR/ticker/f"{ticker}_10K_full.md"
        if not path.exists():
            print(f"{ticker:<7} (file missing)")
            continue
        text=path.read_text()
        sections=split_into_sections(text)
        items=[s["item"] for s in sections if s["item"]]
        no_loss=verify_no_loss(text,sections)
        if not no_loss:
            any_loss=True
        items_str=",".join(items[:12])+("..." if len(items)>12 else "")
        print(f"{ticker:<7} {len(sections):<9} {items_str:<40} {'OK' if no_loss else 'LOST!!'}")
    print("-" * 75)
    if any_loss:
        print("!! CONTENT LOSS detected in some filings - splitter not safe to build on yet.")
    else:
        print("All filings: NO content loss. Splitter is safe to build the chunker on.")
        print("(Filings with few/no items detected still preserve all content in bigger sections.)")


if __name__ == "__main__":
    main()    