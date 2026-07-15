import re

def inspect_company(company:str):
    with open(f"week8/.cache/filings/{company}_docling_full.md","r",encoding="utf-8") as f:
        text=f.read()
    
    print(f"\n{'='*60}\n{company} — full inspection\n{'='*60}")
    matches=list(re.finditer(r"risk\s*factors",text,re.IGNORECASE))
    print(f"Total occurrences:{len(matches)}\n")

    for i,m in enumerate(matches):
        pos=m.start()
        before=text[max(0,pos-30):pos]
        after=text[pos:pos+400]
        print(f"BEFORE:...{before}")
        print(f"AFTER: {after}")
        print()

inspect_company("Morgan_Stanley")