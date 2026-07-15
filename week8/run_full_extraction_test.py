from extract_sections_v2 import split_into_sections_v2
"""
COMPANIES = [
    "Apple", "Microsoft", "Alphabet", "Amazon", "Meta", "JPMorgan",
    "Bank_of_America", "Citigroup", "Goldman_Sachs", "Morgan_Stanley",
    "Pfizer", "Johnson_and_Johnson", "Merck", "AbbVie", "Eli_Lilly",
    "Tesla", "Ford", "Boeing", "Caterpillar", "General_Electric",
]

for company in COMPANIES:
    with open(f"week8/.cache/filings/{company}_docling_full.md", "r", encoding="utf-8") as f:
        text = f.read()
    sections = split_into_sections_v2(text)
    has_1a = "1A" in sections
    has_7 = "7" in sections
    print(f"{company}: {len(sections)} sections | Item 1A: {'✓' if has_1a else '✗'} | Item 7: {'✓' if has_7 else '✗'}")
"""

for company in ["Morgan_Stanley","Citigroup","JPMorgan","Tesla","Ford"]:
    with open(f"week8/.cache/filings/{company}_docling_full.md","r",encoding="utf-8") as f:
        text=f.read()
    sections=split_into_sections_v2(text)

    for key in ["1A","7"]:
        content=sections.get(key,"")
        print(f"\n{company} - Item {key}: {len(content)} chars")
        print(f"  START: {content[:150].strip()}")
        print(f"  END:   {content[-150:].strip()}")
