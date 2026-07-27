"""
XBRL fact extraction via SEC companyfacts API.

XBRL owns numbers. Docling owns prose. Financial facts come from here,
never from table parsing — validated in Week 7/8 that Docling can't
reliably parse SEC's XBRL-tagged tables.

Design:
  - preferred-tag lookup first (broadest total concept, e.g. Revenues),
    pooled across all preferred tags so max(end) picks the current value
  - fuzzy label-match fallback for companies using nonstandard tags
  - every fact carries its source tag (provenance) and unit
  - all annual years retained, deduped by period, for trend/comparison
  - CIK overrides + us-gaap guard for SEC ticker-map quirks
"""


from __future__ import annotations

import requests

HEADERS={"User-Agent":"vishnu vishnuvardhan1920@gmail.com"}

CONCEPT_PREFERRED_TAGS = {
    "revenue":      ["Revenues","RevenueFromContractWithCustomerExcludingAssessedTax"],
    "net_income":   ["NetIncomeLoss"],
    "total_assets": ["Assets"],
}

# Fallback keywords, only used when no preferred tag exists for a company.
CONCEPT_KEYWORDS = {
    "revenue":      ["revenue"],
    "net_income":   ["net income"],   # space, not underscore — matches real labels
    "total_assets": ["assets"],
}

CONCEPT_SYNONYMS={
    "revenue":["revenue","sales","top line","turnover"],
    "net_income":["net income","profit","earnings","bottom line","income"],
    "total_assets":["assets","total assets"],
}

CIK_OVERRIDES = {
    "XOM": "34088",     # map points at ExxonMobil Holdings Corp (fee shell);
                        # real filer is Exxon Mobil Corp
}

def concept_for_query_term(term:str)->str|None:
    t=term.lower().strip()
    for concept,synonyms in CONCEPT_SYNONYMS.items():
        if any(syn in t for syn in synonyms):
            return concept
    return None

_TICKER_MAP:dict[str,str]={}


def fetch_companyfacts(cik:str)->dict:
    cik_padded=cik.zfill(10)
    url = f"https://data.sec.gov/api/xbrl/companyfacts/CIK{cik_padded}.json"
    resp=requests.get(url,headers=HEADERS,timeout=30)
    resp.raise_for_status()
    return resp.json()

def find_matching_tag(facts:dict,keywords:list[str])->list[tuple[str,str]]:
    matches=[]
    for taxonomy,tags in facts.get("facts",{}).items():
        for tag,data in tags.items():
            label=(data.get("label") or "").lower()
            if any(kw in label or kw in tag.lower() for kw in keywords):
                matches.append((taxonomy,tag))
    return matches

def get_concept_values(facts:dict,concept:str)->list[dict]:
    all_taxonomies=facts.get("facts",{})
    pooled_preferred=[]
    for preferred_tag in CONCEPT_PREFERRED_TAGS.get(concept,[]):
        for taxonomy,tags in all_taxonomies.items():
            if preferred_tag in tags:
                units=tags[preferred_tag].get("units",{})
                pooled_preferred.extend({**e,"unit":u,"_source_tag":preferred_tag} for u,entries in units.items() for e in entries)
    if pooled_preferred:
        return pooled_preferred
    
    print(f"NOTE: no preferred tag for '{concept}', falling back to fuzzy match")
    matching=find_matching_tag(facts,CONCEPT_KEYWORDS.get(concept,[]))
    if not matching:
        print(f"WARNING: no tag matched '{concept}', for {facts.get('entityName')}")
        return []
    
    pooled=[]
    for taxonomy,tag in matching:
        units=all_taxonomies[taxonomy][tag].get("units",{})
        pooled.extend({**e,"unit":u,"_source_tag":tag} for u,entries in units.items() for e in entries )
    return pooled

def get_latest_annual_value(facts:dict,concept:str,annual_forms=("10-K","20-F","40-F"))->dict|None:
    values=get_concept_values(facts,concept)
    annual=[v for v in values if v.get("form") in annual_forms]
    if not annual:
        return None
    return max(annual,key=lambda v:v["end"])


def _load_ticekr_map()->dict[str,str]:
    global _TICKER_MAP

    if _TICKER_MAP:
        return _TICKER_MAP
    url = "https://www.sec.gov/files/company_tickers.json"
    data=requests.get(url,headers=HEADERS,timeout=30).json()
    for row in data.values():
        t=row["ticker"].upper()
        if t not in _TICKER_MAP:
            _TICKER_MAP[t]=str(row["cik_str"])
    return _TICKER_MAP

def cik_for_ticker(ticker:str)->str|None:
    t=ticker.upper()
    if t in CIK_OVERRIDES:
        return CIK_OVERRIDES[t]
    return _load_ticekr_map().get(t)

def fetch_by_ticker(ticker:str)->dict|None:
    cik=cik_for_ticker(ticker)
    if cik is None:
        print(f"WARNING: no CIK for ticker {ticker}")
        return None
    facts= fetch_companyfacts(cik)
    usgaap=facts.get("facts",{}).get("us-gaap",{})
    if len(usgaap)<10:
        print(f"WARNING: {ticker} (CIK {cik}) has no us-gaap data "
              f"({facts.get('entityName')}) — likely wrong entity")
        return None
    return facts

def get_all_annual_values(facts:dict,concept:str,annual_forms=("10-K","20-F","40-F"))->list[dict]:
    """
    All annual values for a concept, one per fiscal period, newest first.
    Enables trend/comparison queries. Dedupes by period_end — if a period
    was restated, the later-listed entry wins (the corrected value).
    """
    from datetime import date

    values=get_concept_values(facts,concept)
    annual=[]
    for v in values:
        if v.get("form") not in annual_forms:
            continue
        start,end=v.get("start"),v.get("end")
        if not start or not end:
            annual.append(v)
            continue
        try:
            days=(date.fromisoformat(end)-date.fromisoformat(start)).days
        except (ValueError,TypeError):
            continue
        if v.get("fp")=="FY" and days>350:
            annual.append(v)
    by_period:dict[str,dict]={}
    for v in annual:
        by_period[v["end"]]=v
    return sorted(by_period.values(),key=lambda v:v["end"],reverse=True)

   
if __name__ == "__main__":
    facts = fetch_by_ticker("AAPL")
    print("entity:", facts.get("entityName"))
    for concept in ("revenue", "net_income", "total_assets"):
        print(f"\n{concept}:")
        for v in get_all_annual_values(facts, concept):
            print(f"  {v['end']}  {v['val']:>18,} {v['unit']}  "
                  f"({v['form']})  [{v['_source_tag']}]")



    




            
