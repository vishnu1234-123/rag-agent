from xbrl_companyfacts import fetch_by_ticker
facts = fetch_by_ticker("BRK-B")
usgaap = facts.get("facts", {}).get("us-gaap", {})
print("BRK-B revenue-related tags with 2025 data:")
for tag, data in usgaap.items():
    if "revenue" in tag.lower():
        ends = [e.get("end","") for u in data.get("units",{}).values() for e in u]
        vals = [e.get("val") for u in data.get("units",{}).values() for e in u if e.get("end","")>="2025"]
        if ends and max(ends) >= "2025" and vals:
            print(f"  {tag:<50} latest_val={max(vals)/1e9:.0f}B")
