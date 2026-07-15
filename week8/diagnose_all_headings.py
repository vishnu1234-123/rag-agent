import re
import os

COMPANIES = [
    "Apple", "Microsoft", "Alphabet", "Amazon", "Meta", "JPMorgan",
    "Bank_of_America", "Citigroup", "Goldman_Sachs", "Morgan_Stanley",
    "Pfizer", "Johnson_and_Johnson", "Merck", "AbbVie", "Eli_Lilly",
    "Tesla", "Ford", "Boeing", "Caterpillar", "General_Electric",
]
LOOSE_ITEM = re.compile(r".{0,20}item\s*\d{1,2}[a-c]?\.?.{0,60}", re.IGNORECASE)

for company in COMPANIES:
    path=f"week8/.cache/filings/{company}_docling_full.md"
    if not os.path.exists(path):
        print(f"{company}: FULL MARKDOWN MISSING")
        continue

    with open(path,"r",encoding="utf-8") as f:
        text=f.read()

    matches=LOOSE_ITEM.findall(text)
    matches = LOOSE_ITEM.findall(text)
    print(f"\n{'='*50}\n{company} — {len(matches)} item-like matches found\n{'='*50}")
    for m in matches[:8]:  # first 8 per company, enough to see the pattern
        print(f"  {repr(m)}")


