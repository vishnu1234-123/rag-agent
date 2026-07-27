"""
FilingsIQ - End-to-end dedup check (Week 8, Step 3b)

Wires dedup_triplicated_columns() directly into the real extraction
pipeline and re-runs against Apple's actual 10-K (already downloaded
from Step 2). This confirms the fix works against real Docling table
objects, not just hand-built synthetic DataFrames.

REQUIRES: dedup_columns.py in the same directory (ingestion/).

USAGE (from filingsiq/ repo root):
    python ingestion/inspect_tables_v2.py
"""

from pathlib import Path
from docling.document_converter import DocumentConverter
from dedup_columns import dedup_triplicated_columns,summarize_dedup

RAW_HTML_PATH = Path("data/raw/AAPL/aapl-20250927.htm")

KEYWORDS = {
    "balance sheet": ["total assets", "total liabilities", "shareholders", "stockholders equity"],
    "income statement": ["net sales", "cost of sales", "gross margin", "net income"],
    "cash flow": ["operating activities", "investing activities", "financing activities"],
}

def classify_table(df)->str:
    flat_text=" ".join(str(x).lower() for x in df.values.flatten() if str(x) != "nan")
    for label,kws in KEYWORDS.items():
        if any(kw in flat_text for kw in kws):
            return label
    return ""

def main():
    print("[docling] Converting Apple 10-K (already downloaded)...")
    converter=DocumentConverter()
    result=converter.convert(str(RAW_HTML_PATH))
    doc=result.document

    print(f"[docling] {len(doc.tables)} tables total.\n")

    checked=0
    for i,table in enumerate(doc.tables):
        try:
            df_raw=table.export_to_dataframe(doc)
        except TypeError:
            df_raw=table.export_to_dataframe()

        guess=classify_table(df_raw)

        if not guess:
            continue

        checked+=1
        df_deduped=dedup_triplicated_columns(df_raw)
        print(f"--- Table {i} [{guess.upper()}] ---")
        print(f"  BEFORE dedup: {summarize_dedup(df_raw, df_raw)}")  # just shows shape
        print(f"  AFTER  dedup: {summarize_dedup(df_raw, df_deduped)}")
        print(f"  Preview after dedup (first 3 rows):")
        print(df_deduped.head(3).to_string())
        print()

    print(f"[done] Checked {checked} financial-statement tables end-to-end.")


if __name__ == "__main__":
    main()
