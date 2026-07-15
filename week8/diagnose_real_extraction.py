from extract_sections import extract_section

for company in ["Amazon","Citigroup","Morgan_Stanley","Pfizer","General_Electric","JPMorgan","Bank_of_America"]:
    with open(f"week8/.cache/filings/{company}_docling_full.md","r",encoding="utf-8") as f:
        text=f.read()
    sections=extract_section(text)
    print(f"\n{company}: found {len(sections)} sections -> {list(sections.keys())}")
