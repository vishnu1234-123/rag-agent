"""
FilingsIQ - Prove extraction was fine all along (Week 8, Step 6e)

Hypothesis: the "total_assets 2/20" scare was NOT data loss. Docling
extracted the balance sheet correctly; our reports/*.txt files just
saved a truncated df.head(8) preview of each classified table, and
"Total assets" sits near the BOTTOM of the balance sheet - past row 8 -
so it got cut from the report we were searching.

This script re-extracts ONLY Apple's 10-K, saves the FULL docling text
(no truncation), and greps it for "Total assets" + the known figures.
If found -> extraction was always fine, our diagnostic artifact was the
problem. Cheap, decisive, one filing.

USAGE (from filingsiq/ repo root):
    python ingestion/prove_extraction.py
"""

from pathlib import Path
from docling.document_converter import DocumentConverter
from dedup_columns import dedup_triplicated_columns

RAW=Path("data/raw/AAPL/aapl-20250927.htm")

def main():
    print("[docling] converting Apple 10-K (full,no truncation)...")
    doc=DocumentConverter().convert(str(RAW)).document

    full_md=doc.export_to_markdown()
    Path("data/processed").mkdir(parents=True,exist_ok=True)
    out=Path("data/processed/AAPL_10K_full.md")
    out.write_text(full_md)
    print(f"[saved] full markdown -> {out} ({len(full_md):,} chars)")

    full_table_text=[]
    for i,table in enumerate(doc.tables):
        try:
            df=table.export_to_dataframe(doc)
        except TypeError:
            df=table.export_to_dataframe()

        df=dedup_triplicated_columns(df)
        full_table_text.append(f"--- Table {i} shape={df.shape} ---\n{df.to_string()}\n")
    all_tables="\n".join(full_table_text)
    out2=Path("data/processed/AAPL_10K_alltables.txt")
    out2.write_text(all_tables)
    print(f"[saved] all table rows -> {out2} ({len(all_tables):,} chars)")

    combined=full_md+"\n"+all_tables

    print("\n=== PROOF ====")
    for needle in ["Total assets", "total assets", "364,980", "331,233", "359,241"]:
        present = needle in combined
        print(f"  '{needle}': {'FOUND' if present else 'not found'}")

    # show the actual lines containing "otal assets"
    print("\n=== Lines containing 'otal assets' ===")
    for line in combined.splitlines():
        if "otal assets" in line:
            print(f"  {line.strip()[:120]}")


if __name__ == "__main__":
    main()

