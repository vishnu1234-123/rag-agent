from xbrl_companyfacts import fetch_by_ticker

for ticker in ["BA", "NVDA", "XOM", "T"]:
    facts = fetch_by_ticker(ticker)
    usgaap = facts.get("facts", {}).get("us-gaap", {})
    print(f"\n{ticker} — revenue-ish tags with 2024/2025 data:")
    for tag, data in usgaap.items():
        if "revenue" in tag.lower() or "revenue" in (data.get("label","")).lower():
            ends = [e.get("end","") for u in data.get("units",{}).values() for e in u]
            latest = max(ends) if ends else ""
            if latest >= "2024":   # only current tags
                print(f"  {tag:<55} latest={latest}")
