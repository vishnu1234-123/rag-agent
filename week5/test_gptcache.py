import os
import sys
sys.path.append(os.path.join(os.path.dirname(__file__),'..','week4'))

import requests
import bs4
from dotenv import load_dotenv
from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter

load_dotenv()
os.environ["USER_AGENT"]="rag-agent/1.0"
from pipelines import VanillaRAG

#build apple 10k index

headers={"User-Agent":"rag-agent-research vishnuvardhan1920@gmail.com"}
url = "https://www.sec.gov/Archives/edgar/data/320193/000032019325000079/aapl-20250927.htm"
response=requests.get(url,headers=headers)
response.raise_for_status()

soup=bs4.BeautifulSoup(response.text,"html.parser")
text=soup.get_text()
idx=text.find("PART I")
clean_text=text[idx:]

docs=[Document(page_content=clean_text,meta_data={"source":url})]
splitter=RecursiveCharacterTextSplitter(chunk_size=1500,chunk_overlap=200,add_start_index=True)
apple_splits=splitter.split_documents(docs)

#test semantic cache

pipeline=VanillaRAG(documents=apple_splits,dataset_name="apple_10k")

print("\n"+"="*60)
print("Test 1: first call - expect CACHE MISS")
print("="*60)
result1 = pipeline.run("What was Apple's net income in 2025?")
print(f"Answer: {result1['answer'][:100]}")

print("\n" + "="*60)
print("Test 2: rephrased, same year - expect SEMANTIC CACHE HIT")
print("="*60)
result2 = pipeline.run("Tell me Apple's net income for 2025")
print(f"Answer: {result2['answer'][:100]}")

print("\n" + "="*60)
print("Test 3: same phrasing, different year - expect SEMANTIC NEAR-MISS")
print("="*60)
result3 = pipeline.run("What was Apple's net income in 2024?")
print(f"Answer: {result3['answer'][:100]}")
