import os 
import sys
import requests
from docling.document_converter import DocumentConverter

URL = "https://www.sec.gov/Archives/edgar/data/320193/000032019325000079/aapl-20250927.htm"
LOCAL_PATH = "data/apple_10k_2025.htm"

if not os.path.exists(LOCAL_PATH):
    os.makedirs(os.path.dirname(LOCAL_PATH),exist_ok=True)
    print(f"Downloading from SEC EDGAR...")
    headers={"User-Agent":"rag-agent-research vishnuvardhan1920@gmail.com"}
    response=requests.get(URL,headers=headers)
    response.raise_for_status()
    with open(LOCAL_PATH,"wb") as f:
        f.write(response.content)
    print(f"Saved to {LOCAL_PATH} ({len(response.content)} bytes)")
else:
    print("Using cached {LOCAL_PATH}")

print("Parsing Apple 10-K with Docling...")
print("(First run downloads ML models - takes 1-2 minutes)")

converter=DocumentConverter()
result=converter.convert(LOCAL_PATH)
doc=result.document

#inspect what docling found
print(f"\n=== DOCUMENT STRUCTURE ===")
print(f"Pages: {len(doc.pages) if hasattr(doc, 'pages') else 'N/A (HTML)'}")
print(f"Tables found: {len(doc.tables)}")
print(f"Texts/paragraphs: {len(doc.texts)}")


#show first few tables
print(f"\n=== FIRST 3 TABLES ===")
for i,table in enumerate(doc.tables[:3]):
    print(f"\n--Table {i+1}--")
    print(f"Rows: {table.num_rows if hasattr(table,'num_rows') else 'unknown'}")
    table_md=table.export_to_markdown()
    print(f"Preview:\n{table_md[:500]}")

#show overall document as markdown 
print(f"\n=== DOCUMENT AS MARKDOWN (preview) ===")
md = doc.export_to_markdown()
print(md[:2000])
print(f"\n[Total markdown length: {len(md)} chars]")