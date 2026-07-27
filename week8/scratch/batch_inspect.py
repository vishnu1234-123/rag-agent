"""
FilingsIQ - Batch Extraction Validation (Week 8, Step 2c)

Goal: run the same extraction test across 4 companies x 2 form types
(10-K + 10-Q) = 8 filings, to check whether the "Docling gets the numbers
right, but triplicates columns" finding from Apple's 10-K generalizes,
or whether it's specific to Apple's filing style.

Companies chosen for structural diversity, not just industry:
  - Apple      (tech, clean self-filed HTML)      [already validated once]
  - JPMorgan   (bank - different statement shape, different filing agent)
  - Microsoft  (tech, but different filing agent than Apple)
  - ExxonMobil (energy/industrial - different statement shape again)

USAGE (from filingsiq/ repo root):
    pip install docling requests
    python ingestion/batch_inspect.py

OUTPUT:
    data/raw/<TICKER>/<form>_<period>.htm   <- raw filings, untouched
    stdout                                    <- per-filing summary + flagged tables
"""

import sys
import requests
from pathlib import Path
from docling.document_converter import DocumentConverter

USER_AGENT="FilingsIQ-Research vishnuvardhan1920@gmail.com"

FILINGS = [
    {"ticker": "AAPL", "form": "10-K", "url": "https://www.sec.gov/Archives/edgar/data/320193/000032019325000079/aapl-20250927.htm"},
    {"ticker": "AAPL", "form": "10-Q", "url": "https://www.sec.gov/Archives/edgar/data/320193/000032019326000013/aapl-20260328.htm"},
    {"ticker": "JPM",  "form": "10-K", "url": "https://www.sec.gov/Archives/edgar/data/19617/000162828026008131/jpm-20251231.htm"},
    {"ticker": "JPM",  "form": "10-Q", "url": "https://www.sec.gov/Archives/edgar/data/19617/000162828026029344/jpm-20260331.htm"},
    {"ticker": "MSFT", "form": "10-K", "url": "https://www.sec.gov/Archives/edgar/data/789019/000095017025100235/msft-20250630.htm"},
    {"ticker": "MSFT", "form": "10-Q", "url": "https://www.sec.gov/Archives/edgar/data/789019/000119312526191507/msft-20260331.htm"},
    {"ticker": "XOM",  "form": "10-K", "url": "https://www.sec.gov/Archives/edgar/data/34088/000003408826000045/xom-20251231.htm"},
    {"ticker": "XOM",  "form": "10-Q", "url": "https://www.sec.gov/Archives/edgar/data/34088/000003408826000067/xom-20260331.htm"},
]

KEYWORDS = {
    "balance sheet": ["total assets", "total liabilities", "shareholders", "stockholders equity", "total deposits"],
    "income statement": ["net sales", "cost of sales", "gross margin", "net income", "net interest income", "total revenue", "total revenues"],
    "cash flow": ["operating activities", "investing activities", "financing activities"],
}

def classify_table(df)->str:
    flat_text=" ".join(str(x).lower() for x in df.values.flatten() if str(x)!="nan")
    for label,kws in KEYWORDS.items():
        if any(kw in flat_text for kw in kws):
            return label
    return ""

def looks_triplicated(df)->bool:
    if df.shape[1]<3:
        return False
    try:
        return df.iloc[:,0].equals(df.iloc[:,1]) and df.iloc[:,1].equals(df.iloc[:,2])
    except Exception:
        return False

def fetch(ticker:str,url:str)->Path:
    raw_dir=Path("data/raw")/ticker
    raw_dir.mkdir(parents=True,exist_ok=True)
    fname=url.split("/")[-1]
    path=raw_dir/fname

    if path.exists():
        print(f" [fetch] already have {path} ({path.stat().st_size:,} bytes)")
        return path
    
    print(f" [fetch] downloading {url} ...")
    resp=requests.get(url,headers={"User-Agent":USER_AGENT},timeout=60)
    resp.raise_for_status()
    path.write_bytes(resp.content)
    print(f" [fetch] saved {len(resp.content):,} bytes-> {path}")
    return path

def inspect(ticker:str,form:str,path:Path,report_dir:Path):
    print(f"[docling] converting {path.name} ...")
    converter=DocumentConverter()
    result=converter.convert(str(path))
    doc=result.document
    report_path=report_dir/f"{ticker}_{form.replace('-','')}_tables.txt"
    triplicated_count=0
    matched=0
    with open(report_path,"w") as report:
        report.write(f"Full table dump: {ticker} {form}\n{'='*60}\n\n")
        for i,table in enumerate(doc.tables):
            try:
                df=table.export_to_dataframe(doc)
            except TypeError:
                df=table.export_to_dataframe()
            guess=classify_table(df)

            if guess:
                matched+=1
                trip =looks_triplicated(df)
                if trip:
                    triplicated_count+=1
                report.write(f"--- Table {i} [{guess.upper()}] shape={df.shape} triplicated_cols={trip} ---\n")
                report.write(df.head(10).to_string())
                report.write("\n\n")
    return len(doc.tables),matched,triplicated_count,report_path
    
def main():
    report_dir=Path("reports")
    report_dir.mkdir(exist_ok=True)
    print(f"{'TICKER':<6} {'FORM':<6} {'TOTAL':<7} {'MATCHED':<9} {'TRIPLICATED':<12} REPORT FILE")
    print("-" * 80)

    for f in FILINGS:
        path=fetch(f["ticker"],f["url"])
        total,matched,triplicated,report_path=inspect(f["ticker"],f["form"],path,report_dir)
        flag = f"{triplicated}/{matched}"
        print(f"{f['ticker']:<6} {f['form']:<6} {total:<7} {matched:<9} {flag:<12} {report_path}")


if __name__ == "__main__":
    main()