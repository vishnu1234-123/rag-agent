"""
FilingsIQ - Programmatic CIK + latest filing lookup (Week 8, Step 4)

Replaces manual web-search verification (used for Apple/JPM/MSFT/XOM)
with a direct, scriptable lookup against SEC's own APIs. This is what
the real ingestion pipeline uses going forward - manual search doesn't
scale to 20 companies, let alone quarterly re-runs.

Two SEC endpoints, no API key required:
  1. https://www.sec.gov/files/company_tickers.json
     -> maps ticker symbols to CIK numbers (refreshed by SEC periodically)
  2. https://data.sec.gov/submissions/CIK##########.json
     -> full filing history for a given CIK

USAGE (from filingsiq/ repo root):
    python ingestion/lookup_filings.py

OUTPUT:
    Prints a table: ticker, CIK, form, accession, primary_doc, filing_date
    for the most recent 10-K and 10-Q of each ticker in TICKERS below.
"""

import time
import requests

USER_AGENT = "FilingsIQ-Research YOUR_REAL_EMAIL@example.com"  # <-- EDIT THIS
HEADERS = {"User-Agent": USER_AGENT}

TICKER_MAP_URL = "https://www.sec.gov/files/company_tickers.json"

TICKERS = [
    "AAPL", "MSFT", "JPM", "XOM", "TSLA", "NVDA", "AMZN", "GOOGL", "META",
    "WMT", "JNJ", "UNH", "BRK-B", "PG", "CVX", "BAC", "BA", "V", "KO", "T",
]

KNOWN_GOOD_CIKS = {
    "XOM": 34088,
}


def load_ticker_to_cik_map()->dict:
    resp=requests.get(TICKER_MAP_URL,headers=HEADERS,timeout=30)
    resp.raise_for_status()
    data=resp.json()  # format: {"0": {"cik_str": 320193, "ticker": "AAPL", "title": "Apple Inc."}, ...}


    mapping={}
    for entry in data.values():
        raw_ticker=entry["ticker"].upper()
        mapping[raw_ticker]=entry["cik_str"]
    return mapping

def get_latest_filing(cik:int,form_type:str)->dict|None:
    cik_padded=str(cik).zfill(10)
    url = f"https://data.sec.gov/submissions/CIK{cik_padded}.json"
    resp = requests.get(url, headers=HEADERS, timeout=30)
    resp.raise_for_status()
    data = resp.json()

    recent=data["filings"]["recent"]
    for i,form in enumerate(recent["form"]):
        if form==form_type:
            return{
                "form":form,
                "accessionNumber":recent["accessionNumber"][i],
                "primaryDocument":recent["primaryDocument"][i],
                "filingDate":recent["filingDate"][i],
                "reportDate":recent["reportDate"][i],
            }
    return None

def build_filing_url(cik:int,acession:str,primary_doc:str)->str:
    acc_no_dashes=acession.replace("-","")
    return f"https://www.sec.gov/Archives/edgar/data/{cik}/{acc_no_dashes}/{primary_doc}"

def main():
    print("[lookup ] Downloading SEC ticker->CIK map...")
    ticker_map=load_ticker_to_cik_map()
    print(f"{'TICKER':<8} {'CIK':<12} {'FORM':<6} {'FILED':<12} {'PERIOD':<12} URL")
    print("-" * 120)

    results = []

    for ticker in TICKERS:
        if ticker in KNOWN_GOOD_CIKS:
            cik=KNOWN_GOOD_CIKS[ticker]
        else:
            lookup_key=ticker.replace("-","").replace(".","")
            cik=ticker_map.get(ticker) or ticker_map.get(lookup_key)

        if cik is None:
            print(f"{ticker:<8} NOT FOUND in ticker map - needs manual lookup")
            continue
        for form_type in ["10-K","10-Q"]:
            filing=get_latest_filing(cik,form_type)
            time.sleep(0.15)

            if not filing:
                print(f"{ticker:<8} {cik:<12} {form_type:<6} NOT FOUND in recent filings window (filing={filing!r})")
                continue
            accession = filing.get("accessionNumber")
            primary_doc = filing.get("primaryDocument")
            if not accession or not primary_doc:
                print(f"{ticker:<8} {cik:<12} {form_type:<6} MISSING FIELDS: {filing!r}")
                continue

            url=build_filing_url(cik,filing["accessionNumber"],filing["primaryDocument"])
            print(f"{ticker:<8} {cik:<12} {filing['form']:<6} {filing['filingDate']:<12} {filing['reportDate']:<12} {url}")
            results.append({"ticker": ticker, "cik": cik, **filing, "url": url})

    print(f"\n[done] Resolved {len(results)} filings across {len(TICKERS)} tickers.")
    return results


if __name__ == "__main__":
    main()


