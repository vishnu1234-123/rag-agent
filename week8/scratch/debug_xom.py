from xbrl_companyfacts import fetch_by_ticker, cik_for_ticker

print("XOM CIK:", cik_for_ticker("XOM"))

facts = fetch_by_ticker("XOM")
print("entity:", facts.get("entityName"))
print("top keys:", list(facts.keys()))

taxos = facts.get("facts", {})
print("taxonomies:", list(taxos.keys()))

usgaap = taxos.get("us-gaap", {})
print("us-gaap tag count:", len(usgaap))

# the universal tags — these MUST exist for any real company
for t in ["Assets", "NetIncomeLoss", "Revenues", "Liabilities"]:
    print(f"  '{t}' present: {t in usgaap}")

# if us-gaap is empty, show what IS there
if len(usgaap) < 5:
    print("\nus-gaap nearly empty — showing first 20 tags of whatever exists:")
    for taxo, tags in taxos.items():
        print(f"  taxonomy '{taxo}': {list(tags.keys())[:20]}")
