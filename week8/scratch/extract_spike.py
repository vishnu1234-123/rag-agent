"""
FilingsIQ - Extraction Spike (Week 8, Step 2)

Goal: fetch Apple's FY2025 10-K and test Docling's extraction quality,
specifically on the Item 8 financial statement tables (balance sheet,
income statement, cash flow statement) - the section most likely to
contain dense/XBRL-tagged numeric tables that could break naive parsing.

USAGE (run from your repo root, e.g. filingsiq/):
    pip install docling requests
    python ingestion/extract_spike.py

OUTPUT:
    data/raw/AAPL/aapl-20250927.htm      <- raw filing, untouched
    data/raw/AAPL/docling_output.md      <- Docling's full parsed markdown
    stdout                                <- table-by-table dump for inspection
"""


import sys
import requests
from pathlib import Path

USER_AGENT="FilingsIQ-Research vishnuvardhan1920@gmail.com"

FILING_URL="https://www.sec.gov/Archives/edgar/data/320193/000032019325000079/aapl-20250927.htm"
RAW_DIR=Path("data/raw/AAPL")
RAW_HTML_PATH=RAW_DIR/"aapl-20250927.htm"

def fetch_raw_filing()->None:
    RAW_DIR.mkdir(parents=True,exist_ok=True)

    if RAW_HTML_PATH.exists():
        size=RAW_HTML_PATH.stat().st_size
        print(f"[fetch] Already downloaded: {RAW_HTML_PATH} ({size:,} bytes) - skipping re-download.")
        return
    
    print(f"[fetch] Requesting {FILING_URL} ...")
    resp=requests.get(FILING_URL,headers={"User-Agent":USER_AGENT},timeout=30)
    resp.raise_for_status()
    RAW_HTML_PATH.write_bytes(resp.content)
    print(f"[fetch] Downloaded {len(resp.content):,} bytes -> {RAW_HTML_PATH}")

def extract_with_docling()->None:
    """
    Step 2: run Docling on the raw filing, inspect ONLY the structured
    table output (doc.tables) - this is what actually answers our
    question: do financial statement tables survive extraction intact,
    or come out empty/garbled?
    """

    try:
        from docling.document_converter import DocumentConverter
    except ImportError:
        print("[error] docling is not installed. Run: pip install docling")
        sys.exit(1)

    print("[docling] Converting document (this can take a minute) ...")
    converter=DocumentConverter()
    result=converter.convert(str(RAW_HTML_PATH))
    doc=result.document

    n_tables=len(doc.tables)
    print(f"\n[docling] Detected {n_tables} tables total.\n")

    flagged = []
    for i,table in enumerate(doc.tables):
        print(f"--- Table {i} ---")
        try:
            df=table.export_to_dataframe()
            n_cells=df.size
            n_empty=int(df.isna().sum().sum())+int((df=="").sum().sum())
            pct_empty =(n_empty/n_cells*100) if n_cells else 100.0

            print(f"shape:{df.shape} | empty/NaN cells: {n_empty}/{n_cells} ({pct_empty:.0f}%)")
            print(df.head(8).to_string())

            if pct_empty>30:
                flagged.append(i)
        except Exception as e:
            print(f"[could not export table {i} as dataframe : {e}]")
            flagged.append(i)
        print()

    print("[docling] Done.")

    if flagged:
        print(f"[docling] FLAGGED tables (>30% empty or export error): {flagged}")
        print("[docling] -> Manually compare these against the source filing (Item 8) to confirm if broken.")
    else:
        print("[docling] No tables flagged as suspiciously empty.")
        print("[docling] -> Still manually check that Item 8 numbers match known figures, e.g. Total net sales $416,161M.")


if __name__ == "__main__":
    fetch_raw_filing()
    extract_with_docling()
    

