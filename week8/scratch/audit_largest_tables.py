"""
FilingsIQ - Audit the largest table per category across all 40 filings
(Week 8, Step 5b)

Before hardening the year-distinctness check further, look at ACTUAL data
across all 40 filings (not just the 4-company sample we manually inspected
earlier) to see what year-count patterns really exist. This uses the
same filled-cell-based "largest table" selection logic discussed, and
prints a compact per-filing summary: shape and years found for the
single largest table per category. This is NOT the full validation run -
it's a fast diagnostic pass to inform what the real check should assert.

USAGE (from filingsiq/ repo root):
    python ingestion/audit_largest_tables.py
"""

import json
import re
from pathlib import Path
from docling.document_converter import DocumentConverter
from dedup_columns import dedup_triplicated_columns

FILING_LIST_PATH=Path("data/filing_list.json")

KEYWORDS = {
    "balance sheet": ["total assets", "total liabilities", "shareholders", "stockholders equity", "total deposits"],
    "income statement": ["net sales", "cost of sales", "gross margin", "net income", "net interest income", "total revenue", "total revenues"],
    "cash flow": ["operating activities", "investing activities", "financing activities"],
}
YEAR_PATTERN = re.compile(r"\b(20\d{2})\b")


def classify_table(df) -> str:
    flat_text = " ".join(str(x).lower() for x in df.values.flatten() if str(x) != "nan")
    for label, kws in KEYWORDS.items():
        if any(kw in flat_text for kw in kws):
            return label
    return ""


def count_filled_cells(df) -> int:
    """
    Count cells that aren't NaN and aren't just whitespace/empty string.
    Note: .str accessor only works on a Series, not a whole DataFrame -
    use .map() (applies element-wise across the whole DataFrame) instead
    of trying to vectorize .str.strip() directly on df.
    """
    def is_filled(cell) -> bool:
        if cell is None:
            return False
        s = str(cell).strip()
        return s != "" and s.lower() != "nan"

    return int(df.map(is_filled).sum().sum())
def get_years(df)->set:
    flat_text=" ".join(str(x) for x in df.values.flatten() if str(x)!="nan")
    return set(YEAR_PATTERN.findall(flat_text))

def audit_filing(ticker:str,form:str,path:Path)->list[dict]:
    converter=DocumentConverter()
    result=converter.convert(str(path))
    doc=result.document

    classified=[]
    for i,table in enumerate(doc.tables):
        try:
            df_raw=table.export_to_dataframe(doc)
        except TypeError:
            df_raw=table.export_to_dataframe()
        guess=classify_table(df_raw)
        if guess:
            df_deduped=dedup_triplicated_columns(df_raw)
            classified.append((i,guess,df_deduped))
    
    largest_per_category={}
    for i,guess,df in classified:
        filled=count_filled_cells(df)
        current=largest_per_category.get(guess)
        if current is None or filled>current["filled"]:
            largest_per_category[guess]={"index":i,"shape":df.shape,"filled":filled,"years":sorted(get_years(df))}

    rows=[]
    for guess, info in largest_per_category.items():
        rows.append({
            "ticker": ticker, "form": form, "category": guess,
            "table_index": info["index"], "shape": info["shape"],
            "filled_cells": info["filled"], "n_years": len(info["years"]),
            "years": info["years"],
        })
    return rows    

def main():
    with open(FILING_LIST_PATH) as f:
        filings=json.load(f)
    
    all_rows=[]
    print(f"{'TICKER':<8} {'FORM':<6} {'CATEGORY':<18} {'SHAPE':<12} {'N_YEARS':<8} YEARS")
    print("-" * 90)

    for filing in filings:
        ticker,form,url=filing["ticker"],filing["form"],filing["url"]
        raw_path=Path("data/raw")/ticker/url.split("/")[-1]
        if not raw_path.exists():
            print(f"{ticker:<8} {form:<6} SKIPPED - raw file not found at {raw_path}")
            continue

        rows=audit_filing(ticker,form,raw_path)
        for r in rows:
            all_rows.append(r)
            print(f"{r['ticker']:<8} {r['form']:<6} {r['category']:<18} {str(r['shape']):<12} {r['n_years']:<8} {r['years']}")

    with open("data/year_audit.json","w") as f:
        json.dump(all_rows,f,indent=2)
    print(f"\n[done] Audited {len(all_rows)} primary tables -> data/year_audit.json")

if __name__=="__main__":
    main()
    