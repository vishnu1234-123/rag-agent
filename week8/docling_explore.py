from fetch_filing_doc import fetch_finding_html
import os

CIK="320193"
ACESSION_NO="0000320193-25-000079"

os.makedirs("week8/.cache/filings",exist_ok=True)
local_path="week8/.cache/filings/aapl_10k_2025.htm"

if not os.path.exists(local_path):
    html=fetch_finding_html(CIK,ACESSION_NO)
    with open(local_path,"w",encoding="utf-8") as f:
        f.write(html)
    print(f"Saved to {local_path}")
else:
    print(f"Already cached at {local_path}")

from docling.document_converter import DocumentConverter

converter=DocumentConverter()
result=converter.convert(local_path)

doc=result.document
print("Docling parsed. Exporting to markdown for inspection..")
markdown_output=doc.export_to_markdown()

with open("week8/.cache/filings/aaple_10k_docling_output.md","w",encoding="utf-8") as f:
    f.write(markdown_output)

print(f"Saved Docling output, length: {len(markdown_output)} chars")
print("\nFirst 1000 chars preview:")
print(markdown_output[:1000])

# quick diagnostic - run this snippet
from fetch_filing_doc import get_filing_index, find_main_filing_doc

CIK = "320193"
ACCESSION_NO = "0000320193-25-000079"

index_url = get_filing_index(CIK, ACCESSION_NO)
print("Index URL:", index_url)

filename = find_main_filing_doc(index_url)
print("Selected filename:", filename)