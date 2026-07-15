import os 
from get_latest_10k_acession import get_latest_10k_accession
from fetch_filing_doc import fetch_finding_html
from extract_sections import extract_section

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

os.makedirs("week8/data/prose",exist_ok=True)
os.makedirs("week8/.cache/filings",exist_ok=True)

summary={}

for name,cik in COMPANY_CIK.items():
    print(f"\n--- {name} ---")

    try:
        accession,filed_date=get_latest_10k_accession(cik)
        if not accession:
            summary[name]="NO 10-K FOUND"
            print("-> NO 10-K FOUND")
            continue
        cache_path=f"week8/.cache/filings/{name}_10k.htm"
        if not os.path.exists(cache_path):
            html=fetch_finding_html(cik,accession)
            with open(cache_path,"w",encoding="utf-8") as f:
                f.write(html)
        from docling.document_converter import DocumentConverter
        converter=DocumentConverter()
        result=converter.convert(cache_path)
        markdown_text=result.document.export_to_markdown()
        with open(f"week8/.cache/filings/{name}_docling_full.md","w",encoding="utf-8") as f:
            f.write(markdown_text)
        sections = extract_section(markdown_text)
        risk_factors = sections.get("item_1A", "")
        mda = sections.get("item_7", "")

        for item_key, content in sections.items():
            with open(f"week8/data/prose/{name}_{item_key}.md", "w") as f:
                f.write(content)

        summary[name]=f"risk_factors={len(risk_factors)},mda={len(mda)}"
        print(f"-> {summary[name]}")

    except Exception as e:
        summary[name]=f"ERROR : {e}"
        print(f"-> ERRORL:{e}")

print("\n\n=== DOCLING SUMMARY ===")
for name, status in summary.items():
    print(f"{name}: {status}")