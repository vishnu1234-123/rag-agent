from xbrl_companyfacts import fetch_companyfacts,get_latest_annual_value

facts=fetch_companyfacts("0000012927")
print("Company:",facts.get("entityName"))

for concept in ["revenue","net_income","total_assets"]:
    result=get_latest_annual_value(facts,concept)
    print(f"{concept}:{result}")

facts=fetch_companyfacts("19617")
print("Company:",facts.get("entityName"))

for concept in ["revenue","net_income","total_assets"]:
    result=get_latest_annual_value(facts,concept)
    print(f"{concept}:{result}")