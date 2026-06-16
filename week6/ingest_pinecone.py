import os
import requests
import bs4
from dotenv import load_dotenv
from pinecone import Pinecone
from langchain_openai import OpenAIEmbeddings
from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter

load_dotenv()

#load apple 10k

headers={"User-Agent":"rag-agent-research vishnuvardhan1920@gmail.com"}
url = "https://www.sec.gov/Archives/edgar/data/320193/000032019325000079/aapl-20250927.htm"

print("Fetching Apple 10-K from SEC EDGAR... ")
response=requests.get(url,headers=headers)
response.raise_for_status()

soup=bs4.BeautifulSoup(response.text,"html.parser")
text=soup.get_text()
idx=text.find("PART I")
clean_text=text[idx:]
print(f"Clean text: {len(clean_text):,} characters")

docs=[Document(page_content=clean_text,meta_data={
    "source":url,
    "company":"Apple",
    "filing_type":"10-K",
    "fiscal_year":"2025"
})]

splitter=RecursiveCharacterTextSplitter(
    chunk_size=1500,
    chunk_overlap=200,
    add_start_index=True
)

splits=splitter.split_documents(docs)
print(f"Split into {len(splits)} chunks")

#embed chunks
print("\nEmbedding chunks (this takes a minute)...")
embeddings=OpenAIEmbeddings(model="text-embedding-3-small")
texts=[doc.page_content for doc in splits]
metadata=[doc.metadata for doc in splits]

#embed in batches
batch_size=100
all_embeddings=[]
for i in range(0,len(texts),batch_size):
    batch=texts[i:i+batch_size]
    batch_embeddings=embeddings.embed_documents(batch)
    all_embeddings.extend(batch_embeddings)
    print(f"  Embedded {min(i+batch_size, len(texts))}/{len(texts)} chunks")

#upsert into pinecone
pc=Pinecone(api_key=os.getenv("PINECONE_API_KEY"))
index=pc.Index("filingsiq-dev")

vectors=[]
for i,(text,embedding,metadata) in enumerate(zip(texts,all_embeddings,metadata)):
    vectors.append({
        "id":f"apple-10k-2025-chunk-{i}",
        "values":embedding,
        "metadata":{
            **metadata,
            "text":text
        }
    })

#upsert in batches of 100
for i in range(0,len(vectors),batch_size):
    batch=vectors[i:i+batch_size]
    index.upsert(vectors=batch)
    print(f"  Upserted {min(i+batch_size, len(vectors))}/{len(vectors)} vectors")

stats = index.describe_index_stats()
print(f"\n✅ Done! Total vectors in index: {stats['total_vector_count']}")
