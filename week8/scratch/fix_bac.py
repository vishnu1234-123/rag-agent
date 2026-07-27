import requests
HEADERS = {"User-Agent": "vishnu vishnuvardhan1920@gmail.com"}
data = requests.get("https://www.sec.gov/files/company_tickers.json",
                    headers=HEADERS, timeout=30).json()
print("entries with ticker BAC:")
for row in data.values():
    if row["ticker"].upper() == "BAC":
        print(f"  CIK {row['cik_str']:>10}  {row['title']}")

# and check the real Bank of America Corp facts
from xbrl_companyfacts import fetch_companyfacts
for cik in ["70858", "9661"]:   # test candidates
    try:
        f = fetch_companyfacts(cik)
        rev = f.get("facts",{}).get("us-gaap",{}).get("Revenues") or \
              f.get("facts",{}).get("us-gaap",{}).get("RevenueFromContractWithCustomerExcludingAssessedTax")
        print(f"\nCIK {cik}: {f.get('entityName')}")
        print(f"  has us-gaap tags: {len(f.get('facts',{}).get('us-gaap',{}))}")
    except Exception as e:
        print(f"CIK {cik}: {e}")
