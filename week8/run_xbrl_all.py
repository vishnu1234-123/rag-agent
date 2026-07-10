import json
import os
from xbrl_companyfacts import fetch_companyfacts,get_latest_annual_value

COMPANY_CIK = {
    "Apple": "0000320193", "Microsoft": "0000789019", "Alphabet": "0001652044",
    "Amazon": "0001018724", "Meta": "0001326801", "JPMorgan": "0000019617",
    "Bank_of_America": "0000070858", "Citigroup": "0000831001",
    "Goldman_Sachs": "0000886982", "Morgan_Stanley": "0000895421",
    "Pfizer": "0000078003", "Johnson_and_Johnson": "0000200406",
    "Merck": "0000310158", "AbbVie": "0001551152", "Eli_Lilly": "0000059478",
    "Tesla": "0001318605", "Ford": "0000037996", "Boeing": "0000012927",
    "Caterpillar": "0000018230", "General_Electric": "0000040545",
}

CONCEPTS=["revenue","net_income","total_assets"]
OUTPUT_DIR="week8/data/facts"
os.makedirs(OUTPUT_DIR,exist_ok=True)

summary={}



for name,cik in COMPANY_CIK.items():
    print(f"\n--- {name} ---")
    try:
        facts=fetch_companyfacts(cik)
        entity_name=facts.get("entityName")
        result={"entityName":entity_name,"cik":cik,"facts":{}}

        missing=[]
        for concept in CONCEPTS:
            val=get_latest_annual_value(facts,concept)
            result["facts"]["concept"]=val
            if not val:
                missing.append(concept)
        with open(f"{OUTPUT_DIR}/{name}.json","w") as f:
            json.dump(result,f,indent=2)
        summary[name]="OK" if not missing else f"MISSING : {missing}"
        print(f"-> {summary[name]}")
    except Exception as e:
        summary[name]=f"ERROR: {e}"
        print(f"-> ERROR: {e}")

print("\n\n=== FINAL SUMMARY ===")
for name, status in summary.items():
    print(f"{name}:{status}")