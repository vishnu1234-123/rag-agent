import os
import bs4
import requests
import numpy as np
from dotenv import load_dotenv
from pinecone import Pinecone
from langchain_openai import OpenAIEmbeddings
from rank_bm25 import BM25Okapi
from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter

import cohere

load_dotenv()
#load chunks
headers={"User-Agent":"rag-agent-research vishnuvardhan1920@gmail.com"}
url = "https://www.sec.gov/Archives/edgar/data/320193/000032019325000079/aapl-20250927.htm"
response=requests.get(url,headers=headers)
response.raise_for_status()
soup=bs4.BeautifulSoup(response.text,"html.parser")
text=soup.get_text()
idx=text.find("PART I")
clean_text=text[idx:]
docs=[Document(page_content=clean_text)]
splits=RecursiveCharacterTextSplitter(chunk_size=1500,chunk_overlap=200,add_start_index=True).split_documents(docs)
texts=[doc.page_content for doc in splits]
print(f"Loaded {len(texts)} chunks")

#build bm25 index
tokenized=[t.lower().split() for t in texts]
bm25=BM25Okapi(tokenized)
print("BM25 index built")

#pinecone for dense retrieval
pc=Pinecone(api_key=os.getenv("PINECONE_API_KEY"))
index=pc.Index("filingsiq-dev")
embeddings=OpenAIEmbeddings(model="text-embedding-3-small")

#hybrid search function

def reciprocal_rank_fusion(query:str,top_k:int=3,k:int=60)->list:
    #dense score from pinecone
    query_embedding=embeddings.embed_query(query)
    dense_results=index.query(
        vector=query_embedding,
        top_k=len(texts),
        include_metadata=True
    )
    dense_ranking={}
    #build dense score map 
    for rank,match in enumerate(dense_results["matches"]):
        chunk_idx=int(match["id"].split("-")[-1])
        dense_ranking[chunk_idx]=rank+1
    
    #bm25 scores
    bm25_scores=bm25.get_scores(query.lower().split())
    bm25_ranking={}
    for rank,idx in enumerate(np.argsort(bm25_scores)[::-1]):
        bm25_ranking[int(idx)]=rank+1
    
    #rrf scores
    rrf_scores={}
    for i in range(len(texts)):
        dense_rank=dense_ranking.get(i,len(texts))
        bm25_rank=bm25_ranking.get(i,len(texts))
        rrf_scores[i]=1/(k+dense_rank)+1/(k+bm25_rank)
    #sort rrf scores
    top_indices=sorted(rrf_scores,key=rrf_scores.get,reverse=True)[:top_k]
    return [(texts[i],rrf_scores[i],dense_ranking.get(i),bm25_ranking.get(i)) for i in top_indices]

co=cohere.Client(api_key=os.getenv("COHERE_API_KEY"))
def hybrid_rerank(query:str,final_k:int=3)->list:
    rrf_results=reciprocal_rank_fusion(query,top_k=10)
    candidates=[text for text,rrf_score,dense_rank,bm25_rank in rrf_results]
    reranked=co.rerank(
        query=query,
        documents=candidates,
        top_n=final_k,
        model="rerank-english-v3.0"
    )
    results=[]
    for result in reranked.results:
        text=(result.document.text if result.document and result.document.text else candidates[result.index])
        results.append((text,result.relevance_score))
    return results
# ── 5. compare dense vs hybrid ────────────────────────────────────────────
questions = [
    "What was Apple's net income in 2025?",
    "What are Apple's main risk factors?",
    "What products did Apple release in Q2 2025?"
]

for q in questions:
    print(f"\n{'='*70}")
    print(f"Query: {q}")
    print(f"{'='*70}")

    print("\n--- DENSE ONLY ---")
    query_embedding = embeddings.embed_query(q)
    dense_results = index.query(vector=query_embedding, top_k=3, include_metadata=True)
    for i, match in enumerate(dense_results["matches"]):
        print(f"  [{i+1}] score={match['score']:.3f} | {match['metadata']['text'][:120]}...")

    print("\n--- RRF HYBRID (top 10 → show top 3) ---")
    rrf_results = reciprocal_rank_fusion(q, top_k=3)
    for i, (text, rrf_score, dense_rank, bm25_rank) in enumerate(rrf_results):
        print(f"  [{i+1}] rrf={rrf_score:.4f} dense_rank={dense_rank} "
              f"bm25_rank={bm25_rank} | {text[:120]}...")
     
    print("\n--- RRF + COHERE RERANK (top 10 → reranked → top 3) ---")
    reranked = hybrid_rerank(q, final_k=3)
    for i, (text, score) in enumerate(reranked):
        print(f"  [{i+1}] relevance={score:.4f} | {text[:120]}...")
    