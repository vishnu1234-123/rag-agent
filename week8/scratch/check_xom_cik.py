import requests
HEADERS = {"User-Agent": "vishnu vishnuvardhan1920@gmail.com"}
data = requests.get("https://www.sec.gov/files/company_tickers.json",
                    headers=HEADERS, timeout=30).json()
print("all entries with ticker XOM:")
for row in data.values():
    if row["ticker"].upper() == "XOM":
        print(f"  CIK {row['cik_str']:>10}  {row['title']}")
