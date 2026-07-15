import re

for company in ["Amazon","Citigroup","Morgan_Stanley","General_Electric"]:
    with open(f"week8/.cache/filings/{company}_docling_full.md","r",encoding="utf-8") as f:
        text=f.read()

    print(f"\n{'='*50}\n{company}\n{'='*50}")

    matches=list(re.finditer(r"1A.{0,200}",text,re.IGNORECASE))
    risk_nearby=[m for m in matches if "risk" in m.group().lower()]
    print(f"'1A' + 'risk' nearby: {len(risk_nearby)} matches")

    for m in risk_nearby[:3]:
        print(f" {repr(m.group())}")

    if not risk_nearby:
        rf_matches=list(re.finditer(r".{50}risk\s*factors.{50}",text,re.IGNORECASE))
        print(f"'risk factors' anywhere: {len(rf_matches)} matches")
        for m in rf_matches[:3]:
            print(f"{repr(m.group())}")