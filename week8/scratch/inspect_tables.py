"""
FilingsIQ - Follow-up inspection script (Week 8, Step 2b)

Our first pass flagged 58/62 tables as >30% empty, but the ones we
actually looked at (60, 61) were the signature block - sparse by nature,
not broken. We need to find the ACTUAL financial statement tables
(balance sheet, income statement, cash flow) and check those specifically,
rather than eyeballing all 62 or trusting a blind threshold.

This script:
  1. Re-uses the already-downloaded raw filing (does not re-fetch)
  2. Runs Docling once
  3. For each table, checks if its content looks like a balance sheet,
     income statement, or cash flow statement (by keyword match)
  4. Only prints those - so we see exactly the tables that matter

USAGE (from filingsiq/ repo root):
    python ingestion/inspect_tables.py
"""

from pathlib import Path
from docling.document_converter import DocumentConverter

RAW_HTML_PATH = Path("data/raw/AAPL/aapl-20250927.htm")

KEYWORDS={
    "balance sheet":["total assets","total liabilities","shareholders","stockholders equity"],
    "income statement":["net sales","cost of sales","gross margin","net income"],
    "cash flow":["operating activities","investing activities","financing activites"],
}

def classify_table(df)->str:
    flat_text=" ".join(str(x).lower() for x in df.values.flatten() if str(x)!="nan")
    for label,kws in KEYWORDS.items():
        if any(kws in flat_text for kws in kws):
            return label
    return ""

def main():
    print("[docling] Converting document...")
    converter=DocumentConverter()
    result=converter.convert(str(RAW_HTML_PATH))
    doc=result.document

    print(f"[docling] {len(doc.tables)} tables total.\n")

    for i,table in enumerate(doc.tables):
        try:
            df=table.export_to_dataframe(doc)
        except TypeError:
            df=table.export_to_dataframe()
        
        guess=classify_table(df)

        if guess:
            n_cells=df.size
            n_empty=int(df.isna().sum().sum())+int((df=="").sum().sum())
            pct_empty=(n_empty/n_cells*100) if n_cells else 100.0
            print(f"--- Table {i}  [LIKELY: {guess.upper()}]  shape={df.shape}  empty={pct_empty:.0f}% ---")
            print(df.head(10).to_string())
            print()


if __name__ == "__main__":
    main()
