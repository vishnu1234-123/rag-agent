from xbrl_companyfacts import fetch_by_ticker, cik_for_ticker, get_latest_annual_value

# known-correct FY2024/2025 revenue, from public sources, in billions
KNOWN_REVENUE_B = {
    "AAPL": 416, "MSFT": 282, "AMZN": 717, "GOOGL": 403, "META": 201,
    "NVDA": 216, "TSLA": 95, "JPM": 182, "BAC": 102, "WMT": 706,
    "XOM": 332, "CVX": 184, "JNJ": 94, "UNH": 448, "V": 39,
    "KO": 48, "PG": 84, "T": 126, "BA": 89, "BRK-B": 371,
}

for ticker, expected_b in KNOWN_REVENUE_B.items():
    facts = fetch_by_ticker(ticker)
    print(f"{ticker:<6} entity={facts.get('entityName')[:35]:<35} CIK={cik_for_ticker(ticker)}")
    v = get_latest_annual_value(facts, "revenue")
    if v:
        got_b = v["val"] / 1e9
        off = abs(got_b - expected_b) / expected_b * 100
        flag = "  <-- CHECK" if off > 5 else "  ok"
        print(f"       revenue got={got_b:>7.1f}B  expected~{expected_b}B  ({off:.0f}% off){flag}")
