from xbrl_companyfacts import fetch_companyfacts, get_concept_values

facts = fetch_companyfacts("320193")
print("entity:", facts.get("entityName"))
print("top-level keys:", list(facts.keys()))
print("taxonomies:", list(facts.get("facts", {}).keys()))

# does the exact 'Assets' tag exist where we expect?
usgaap = facts.get("facts", {}).get("us-gaap", {})
print("\nus-gaap tag count:", len(usgaap))
print("'Assets' present:", "Assets" in usgaap)
print("'NetIncomeLoss' present:", "NetIncomeLoss" in usgaap)

# what does get_concept_values actually return?
vals = get_concept_values(facts, "total_assets")
print(f"\nget_concept_values('total_assets') returned {len(vals)} entries")
if vals:
    print("first entry keys:", list(vals[0].keys()))
    print("first entry:", {k: vals[0][k] for k in list(vals[0])[:8]})
    forms = set(v.get("form") for v in vals)
    print("forms present:", forms)
