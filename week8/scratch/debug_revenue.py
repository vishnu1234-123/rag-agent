from xbrl_companyfacts import fetch_by_ticker, get_concept_values

for ticker in ["BA", "NVDA", "XOM"]:
    facts = fetch_by_ticker(ticker)
    vals = get_concept_values(facts, "revenue")
    annual = [v for v in vals if v.get("form") == "10-K"]
    # show which tags are in play and their latest dates
    from collections import defaultdict
    by_tag = defaultdict(list)
    for v in vals:
        by_tag[v.get("_source_tag", "PREFERRED")].append(v.get("end"))
    print(f"\n{ticker}: {len(vals)} revenue entries across tags:")
    for tag, ends in by_tag.items():
        print(f"  {tag:<55} latest={max(ends)}")
