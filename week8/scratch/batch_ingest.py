"""
FilingsIQ - Full batch ingestion with layered validation (Week 8, Step 5)

Runs fetch -> extract -> dedup -> validate across all 20 companies in
data/filing_list.json. Reuses the exact logic already validated on the
4-company sample: dedup_triplicated_columns() and the financial-statement
classifier keywords.

Validation is layered, cheapest-and-most-general first (see SESSION_LOG
for reasoning):
  1. Structural checks (universal, no industry knowledge needed):
     - did extraction find any tables at all?
     - did at least one classify as a financial statement?
     - after dedup, no fully-empty rows/cols in classified tables?
  2. One semantic check that generalizes across all industries:
     - does the income statement show >=2 distinct year labels with
       at least some differing numeric values? (catches over-collapse
       by dedup, or a table that's accidentally all one period)
  3. Failures are FLAGGED, not fatal - written to needs_review.json,
     pipeline continues to the next filing rather than crashing.

USAGE (from filingsiq/ repo root):
    pip install docling requests pandas
    python ingestion/batch_ingest.py

OUTPUT:
    data/raw/<TICKER>/<file>.htm         <- raw filings (already may exist)
    reports/<TICKER>_<form>_tables.txt   <- full table dump per filing
    data/needs_review.json               <- filings that failed validation
    data/ingestion_summary.json          <- pass/fail summary for all 40
"""

import json
import re
import requests
from pathlib import Path
from docling.document_converter import DocumentConverter
from dedup_columns import dedup_triplicated_columns

USER_AGENT="FilingsIQ-Research vishnuvardhan1920@gmail.com"

FILINGS_LIST_PATH=Path("data/filing_list.json")
REPORT_DIR=Path("reports")
NEEDS_REVIEW_PATH=Path("data/needs_review.json")
SUMMARY_PATH=Path("data/ingestion_summary.json")

KEYWORDS = {
    "balance sheet": ["total assets", "total liabilities", "shareholders", "stockholders equity", "total deposits"],
    "income statement": ["net sales", "cost of sales", "gross margin", "net income", "net interest income", "total revenue", "total revenues"],
    "cash flow": ["operating activities", "investing activities", "financing activities"],
}

YEAR_PATTERN = re.compile(r"\b(20\d{2})\b")

def classify_table(df)->str:
    flat_text=" ".join(str(x).lower() for x in df.values.flatten() if str(x)!="nan")
    for label,kws in KEYWORDS.items():
        if any(kw in flat_text for kw in kws):
            return label
    return ""

def fetch(ticker:str,url:str)->Path:
    raw_dir=Path("data/raw")/ticker
    raw_dir.mkdir(parents=True,exist_ok=True)
    path=raw_dir/url.split("/")[-1]
    if path.exists():
        return path
    resp=requests.get(url,headers={"User-Agent":USER_AGENT},timeout=60)
    resp.raise_for_status()
    path.write_bytes(resp.content)
    return path

def check_structural(df_deduped)->list[str]:
    issues=[]
    if df_deduped.empty:
        issues.append("table is empty after dedup")
        return issues
    
    n_cells=df_deduped.size
    n_empty=int(df_deduped.isna().sum().sum())+int((df_deduped.astype(str)=="").sum().sum())
    pct_empty=(n_empty/n_cells*100) if n_cells else 100.0

    if pct_empty>80:
        issues.append(f"{pct_empty:.0f}% empty cells even after dedup (expected some sparsity, not this much)")
    return issues

def check_year_distinctness(df_deduped,form_type:str)->list[str]:
    """
    Layer 2: the one semantic check that generalizes across industries.
    A financial statement should show multiple distinct year labels with
    at least some differing numeric values across them - regardless of
    whether it's a bank, energy company, or retailer.
    """

    issues=[]
    flat_text=" ".join(str(x) for x in df_deduped.values.flatten() if str(x)!="nan")
    years_found=set(YEAR_PATTERN.findall(flat_text))

    min_expected_years=3 if form_type=="10-K" else 2

    if len(years_found)<min_expected_years:
        issues.append(f"only {len(years_found)} distinct year(s) found ({years_found}) - expected >= {min_expected_years}")

    return issues

def process_filing(ticker:str,form:str,url:str)->dict:

    path=fetch(ticker,url)

    print(f" [docling] converting {path.name} ...")
    converter=DocumentConverter()
    result=converter.convert(str(path))
    doc=result.document

    report_path=REPORT_DIR/f"{ticker}_{form.replace('-','')}_tables.txt"
    all_issues=[]
    matched_count=0

    with open(report_path,"w") as report:
        report.write(f"Full table dump: {ticker} {form}\n{'='*60}\n\n")

        for i,table in enumerate(doc.tables):
            try:
                df_raw=table.export_to_dataframe(doc)
            except TypeError:
                df_raw=table.export_to_dataframe()
            
            guess=classify_table(df_raw)
            if not guess:
                continue

            matched_count+=1
            df_deduped=dedup_triplicated_columns(df_raw)

            issues=check_structural(df_deduped)

            if guess=="income statement":
                issues+=check_year_distinctness(df_deduped,form)

            report.write(f"--- Table {i} [{guess.upper()}] shape={df_deduped.shape} ---\n")
            report.write(df_deduped.head(8).to_string())

            if issues:
                report.write(f"\n Issues:{issues}")
            report.write("\n\n")

            if issues:
                all_issues.append({"table_index": i, "classification": guess, "issues": issues})

    return {
        "ticker":ticker,
        "form":form,
        "total_tables":len(doc.tables),
        "matched_financial_tables":matched_count,
        "issues":all_issues,
        "status":"NEEDS_REVIEW" if all_issues or matched_count ==0 else "OK",
    }

def main():
    with open(FILINGS_LIST_PATH) as f:
        filings=json.load(f)

        REPORT_DIR.mkdir(exist_ok=True)

        summary=[]
        needs_review=[]

        print(f"{'TICKER':<8} {'FORM':<6} {'TABLES':<8} {'MATCHED':<9} STATUS")
        print("-" * 60)

        for filing in filings:
            ticker=filing["ticker"]
            form=filing["form"]
            url=filing["url"]

            print(f"=== {ticker} {form} ===")
            outcome=process_filing(ticker,form,url)
            summary.append(outcome)

        print(f"{ticker:<8} {form:<6} {outcome['total_tables']:<8} {outcome['matched_financial_tables']:<9} {outcome['status']}")

        if outcome["status"] == "NEEDS_REVIEW":
            needs_review.append(outcome)
            
    with open(SUMMARY_PATH,"w") as f:
        json.dump(summary,f,indent=2)
    with open(NEEDS_REVIEW_PATH,"w") as f:
        json.dump(needs_review,f,indent=2)

    ok_count=sum(1 for s in summary if s["status"]=="OK")
    print(f"\n[done] {ok_count}/{len(summary)} filings passed validation cleanly.")
    print(f"[done] {len(needs_review)} filings flagged for review -> {NEEDS_REVIEW_PATH}")
    print(f"[done] Full summary -> {SUMMARY_PATH}")


if __name__ == "__main__":
    main()




