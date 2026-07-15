import re

for company in ["Amazon","Citigroup","Morgan_Stanley","General_Electric"]:
    with open(f"week8/.cache/filings/{company}_docling_full.md","r",encoding="utf-8") as f:
        text=f.read()

    print(f"\n{'='*50}\n{company} (doc length: {len(text)} chars)\n{'='*50}")

    matches=list(re.finditer(r"risk\sfactors",text,re.IGNORECASE))
    print(f"Total 'risk factors' occurrences: {len(matches)}")
    for m in matches:
        position_pct=(m.start()/len(text))*100
        context=text[max(0,m.start()-60):m.start()+80]
        print(f" at {position_pct:.1f}% through doc :{repr(context)}")
      