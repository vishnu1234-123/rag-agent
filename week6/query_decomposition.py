import os 
import sys
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'week4'))

import numpy as np
import requests
import bs4
import cohere
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI,OpenAIEmbeddings
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_core.output_parsers import StrOutputParser
from pinecone import Pinecone
from rank_bm25 import BM25Okapi

load_dotenv()

#load chunk
headers={"User-Agent":"rag-agent-research vishnuvardhan1920@gmail.com"}
url = "https://www.sec.gov/Archives/edgar/data/320193/000032019325000079/aapl-20250927.htm"
response=requests.get(url,headers=headers)
soup=bs4.BeautifulSoup(response.text,"html.parser")
text=soup.get_text()
clean_text=text[text.find("PART I"):]
docs=[Document(page_content=clean_text)]
splits=RecursiveCharacterTextSplitter(chunk_size=1500,chunk_overlap=200).split_documents(docs)
texts=[doc.page_content for doc in splits]
print(f"Loaded {len(texts)} chunks")

#setup retrieval
tokenized=[t.lower().split() for t in texts]
bm25=BM25Okapi(tokenized)

pc=Pinecone(api_key=os.getenv("PINECONE_API_KEY"))
index=pc.Index("filingsiq-dev")
embeddings=OpenAIEmbeddings(model="text-embedding-3-small")
co=cohere.ClientV2(api_key=os.getenv("COHERE_API_KEY"))
llm=ChatOpenAI(model="gpt-4o-mini",temperature=0)

#retrieval helpers
def reciprocal_rank_fusion(query:str,top_k:int=10)->list:
    query_embedding=embeddings.embed_query(query)
    dense_results=index.query(
        vector=query_embedding,
        top_k=len(texts),
        include_metadata=True
    )

    dense_ranking={
        int(idx["id"].split("-")[-1]):rank+1 for rank,idx in enumerate(dense_results["matches"])
    }

    bm25_scores=bm25.get_scores(query.lower().split())
    bm25_ranking={
        int(idx):rank+1 for rank,idx in enumerate(np.argsort(bm25_scores)[::-1])
    }

    rrf_scores={

        i:1/(60+dense_ranking.get(i,len(texts)))+1/(60+bm25_ranking.get(i,len(texts))) for i in range(len(texts))
    }

    top_indices=sorted(rrf_scores,key=rrf_scores.get,reverse=True)[:top_k]
    return [texts[i] for i in top_indices]

def retrieve_and_rerank(query:str,top_k:int=3)->list:
    candidates=reciprocal_rank_fusion(query,top_k=10)
    reranked=co.rerank(
        query=query,
        documents=candidates,
        top_n=top_k,
        model="rerank-english-v3.0",
        
    )

    return[
       candidates[r.index] for r in reranked.results
    ]

#query decompostion
DECOMPOSE_PROMPT=ChatPromptTemplate.from_template("""
You are an expert at breaking down complex questions about SEC filings
into simple, focused sub-questions that can each be answered by searching
a single document section.

Break this question into 2-4 specific sub-questions.
Return ONLY the sub-questions, one per line,no numbering or bullets.
Each sub-question should be self-contained and searchable.
Question:{question}   
Sub-questions:""")
decompose_chain=DECOMPOSE_PROMPT|llm|StrOutputParser()

def decompose_query(question:str)->list[str]:
    result=decompose_chain.invoke({"question":question})
    sub_queries=[q.strip() for q in result.strip().split("\n") if q.strip()]
    return sub_queries

GENERATE_PROMPT=ChatPromptTemplate.from_template(""" 
You are an expert analyst answering questions about Apple's SEC filings.
Use ONLY the provided context to answer the question.
If the context doesnt contain enough information,say so explicitly.
                                                 
Context:{context}
Question:{question}
Answer:
""")

generate_chain=GENERATE_PROMPT|llm|StrOutputParser()

# full decompostion pipeline
def decomposed_rag(question:str)->dict:
    print(f"\nOriginal query:{question}")

    #decompose
    sub_queries=decompose_query(question)
    print(f"\n Decompose into {len(sub_queries)} sub-queries:")
    for i,q in enumerate(sub_queries):
        print(f"{i+1}:{q}")
    
    all_contexts=[]

    seen=set()
    for sub_q in sub_queries:
        chunks=retrieve_and_rerank(sub_q,top_k=2)
        for chunk in chunks:
            if chunk not in seen:
                all_contexts.append(chunk)
                seen.add(chunk)
    
    print(f"\nTotal unique chunks retrieved: {len(all_contexts)}")

    #generate final answer
    answer=generate_chain.invoke({
        "context":"\n\n---\n\n".join(all_contexts),
        "question":question
    })
    return{
        "question":question,
        "sub_queries":sub_queries,
        "num_contexts":len(all_contexts),
        "answer":answer
    }


    # ── 6. test ───────────────────────────────────────────────────────────────
test_questions = [
    "How did Apple's revenue and net income change from 2023 to 2025, and what were the main drivers?",
    "What are Apple's main risk factors and how does the company plan to address them?",
]

for q in test_questions:
    print("\n" + "="*70)
    result = decomposed_rag(q)
    print(f"\nFINAL ANSWER:\n{result['answer']}")
    print(f"\n({result['num_contexts']} chunks used from "
          f"{len(result['sub_queries'])} sub-queries)")