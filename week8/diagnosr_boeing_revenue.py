from xbrl_companyfacts import fetch_companyfacts

facts=fetch_companyfacts("0000012927")
us_gaap=facts.get("facts",{}).get("us-gaap",{})

for tag,data in us_gaap.items():
    label=data.get("label") or ""
    
    if "revenue" in tag.lower() or "revenue" in label.lower():
        units=data.get("units",{})
        for unit_code,entries in units.items():
            annual=[e for e in entries if e.get("form") in ("10-K","20-F","40-F")]
            if annual:
                latest=max(annual,key= lambda e:e["end"])
                print(f"{tag} ({label}) -> latest: {latest['end']}, val: {latest['val']:,}")