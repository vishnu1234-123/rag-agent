"""
FilingsIQ - Clean extraction + full-text cache for all 40 filings
(Week 8, Step 7)

Single responsibility: fetch -> Docling extract -> dedup tables -> save
the FULL output per filing. No validation logic here (that reads these
saved files separately). This is both the real ingestion artifact that
chunking consumes AND the extraction cache (so chunking / re-validation
never re-runs the expensive Docling step).

For each filing, saves two files under data/processed/<TICKER>/:
  <TICKER>_<form>_full.md       -> export_to_markdown: narrative + tables
                                   in reading order. THIS is what chunking
                                   consumes.
  <TICKER>_<form>_tables.txt    -> every table, ALL rows (deduped), for
                                   number-level validation (XBRL cross-check).

Idempotent: skips a filing if both output files already exist.

USAGE (from filingsiq/ repo root):
    python ingestion/extract_all.py
"""

import json
import requests
from pathlib import Path
from docling.document_converter import DocumentConverter
from dedup_columns import dedup_triplicated_columns

USER_AGENT = "FilingsIQ-Research YOUR_REAL_EMAIL@example.com"  # <-- EDIT THIS
FILING_LIST_PATH = Path("data/filing_list.json")
PROCESSED_DIR = Path("data/processed")


def fetch(ticker: str, url: str) -> Path:
    raw_dir = Path("data/raw") / ticker
    raw_dir.mkdir(parents=True, exist_ok=True)
    path = raw_dir / url.split("/")[-1]
    if path.exists():
        return path
    resp = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=60)
    resp.raise_for_status()
    path.write_bytes(resp.content)
    return path

def extract_one(ticker:str,form:str,raw_path:Path)->tuple[Path,Path]:
    out_dir=PROCESSED_DIR/ticker
    out_dir.mkdir(parents=True,exist_ok=True)
    form_tag=form.replace("-","")
    md_path=out_dir/f"{ticker}_{form_tag}_full.md"
    tables_path=out_dir/f"{ticker}_{form_tag}_tables.txt"

    if md_path.exists() and tables_path.exists():
        print(f"[skip] {ticker} {form} already extracted")
        return md_path,tables_path
    
    print(" [docling] converting {raw_path.name}")
    doc=DocumentConverter().convert(str(raw_path)).document

    md_path.write_text(doc.export_to_markdown())

    parts=[]
    for i,table in enumerate(doc.tables):
        try:
            df=table.export_to_dataframe(doc)
        except TypeError:
            df=table.export_to_dataframe()
        
        df=dedup_triplicated_columns(df)
        parts.append(f"--- Table {i} shape={df.shape} ---\n{df.to_string()}\n")
    tables_path.write_text("\n".join(parts))

    print(f"  [saved] {md_path.name} ({md_path.stat().st_size:,}B), "
          f"{tables_path.name} ({tables_path.stat().st_size:,}B)")
    return md_path, tables_path

def main():
    with open(FILING_LIST_PATH) as f:
        filings=json.load(f)
    
    print(f"Extracting {len(filings)} filings -> {PROCESSED_DIR}/\n")

    for filing in filings:
        ticker,form,url=filing["ticker"],filing["form"],filing["url"]
        print(f"=== {ticker} {form} ===")
        raw_path=fetch(ticker,url)
        extract_one(ticker,form,raw_path)
    
    print(f"\n[done] All filings extracted to {PROCESSED_DIR}/")

if __name__=="__main__":
    main()