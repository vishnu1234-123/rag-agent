import requests

HEADERS={
    "User-Agent":"vishnu vishnuvardhan1920@gmail.com"
}
CONCEPT_PREFERRED_TAGS={
    "revenue":["RevenueFromContractWithCustomerExcludingAssessedTax", "Revenues"],
    "net_income":["NetIncomeLoss"],
    "total_assets":["Assets"],
}
CONCEPT_KEYWORDS={
    "revenue":["revenue"],
    "net_income":["net income"],
    "total_assets":["assets"], 
}

def fetch_companyfacts(cik:str)->dict:
    cik_padded=cik.zfill(10)
    url=f"https://data.sec.gov/api/xbrl/companyfacts/CIK{cik_padded}.json"
    resp=requests.get(url,headers=HEADERS)
    resp.raise_for_status()
    return resp.json()

def find_matching_tag(facts:dict,keywords:list[str])->list[tuple[str,str]]:
    matches=[]
    """main facts contain three keys: 
     cik : company specific code
     entityName: Name of the comapany
     facts: contains all the numerical information"""
    all_taxonomies=facts.get("facts",{}) 
    #print(all_taxonomies.items())
   
    for taxonomy,tags in all_taxonomies.items():
        for tag,data in tags.items():
            label=data.get("label","") or ""
            search_text=(label+" "+tag).lower()
            if any(kw.lower() in search_text for kw in keywords):
                matches.append((taxonomy,tag))
    return matches

def get_concept_values(facts:dict,concept:str)->list[dict]:
    all_taxonomies=facts.get("facts",{})
    pooled=[]
    for preferred_tag in CONCEPT_PREFERRED_TAGS.get(concept,[]):
        for taxonomy,tags in all_taxonomies.items():
            if preferred_tag in tags:
                units=tags[preferred_tag].get("units",{})
                pooled.extend({**e,"unit":u,"_source_tag":preferred_tag} for u,entries in units.items() for e in entries)
    if pooled:
        return pooled
    print(f"NOTE: no preferred tag found for '{concept}', falling back to fuzzy match")

    keywords=CONCEPT_KEYWORDS.get(concept,[])
    matching=find_matching_tag(facts,keywords)

    if not matching:
        print(f"WARNING: no tag matched concept='{concept}' for {facts.get('entityName')} (keywords={keywords})")
        return []
    
    pooled_values = []
    for taxonomy, tag in matching:
        units = all_taxonomies[taxonomy][tag].get("units", {})
        pooled_values.extend({**e, "unit": u, "_source_tag": tag} for u, entries in units.items() for e in entries)
    return pooled_values
    
def get_latest_annual_value(facts:dict,concept:str,annual_forms=("10-K","20-F","40-F"))->dict|None:
    values=get_concept_values(facts,concept)
    annual=[v for v in values if v.get("form") in annual_forms]
    if not annual:
        return None
    return max(annual,key=lambda v:v["end"])

