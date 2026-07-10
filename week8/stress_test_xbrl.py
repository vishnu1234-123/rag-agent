from xbrl_companyfacts import fetch_companyfacts,get_latest_annual_value

STRESS_TEST_COMPANIES= {
    "Johnson_and_Johnson":"0000200406",
    "Boeing":"0000012927",
    "Bank_of_America":"0000070858",
    "Microsoft":"0000789019",
    "Tesla":"0001318605",
}

CONCEPTS=["revenue","net_income","total_assets"]

results={}

for name,cik in STRESS_TEST_COMPANIES.items():
    print(f"\n{'='*50}")
    print(f"Testing: {name} (CIK:{cik})")
    print('='*50)

    try:
        facts=fetch_companyfacts(cik)
        print(f"Company confirmed: {facts.get('entityName')}")

        company_results={}
        for concept in CONCEPTS:
            value=get_latest_annual_value(facts,concept)
            company_results[concept]=value
            if value:
                print(f"{concept}:${value['val']:,}({value['unit']},period end {value['end']})")
            else:
                print(f"{concept}:NO VALUE FOUND")
            results[name]=company_results
    except Exception as e:
        print(f"ERROR fetching {name}:{e}")
        results[name]=None
print(f"\n\n{'='*50}")
print("SUMMARY")
print('='*50)

for name,res in results.items():
    if res is None:
        print(f"{name}:FETCH FAILED")
    else:
        missing=[c for c in CONCEPTS if not res.get(c)]
        if missing:
            print(f"{name}:missing {missing}")
        else:
            print(f"{name}: all concepts resolved")
