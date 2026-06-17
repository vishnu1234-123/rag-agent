import os 
import sys
sys.path.append(os.path.join(os.path.dirname(__file__),'..','week4'))

import numpy as np
import requests
import bs4
import time
import cohere
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI,OpenAIEmbeddings
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter
from pinecone import Pinecone
from rank_bm25 import BM25Okapi

load_dotenv()

#load chunks

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

#setup
tokenized=[t.lower().split() for t in texts]
bm25=BM25Okapi(tokenized)
pc=Pinecone(api_key=os.getenv("PINECONE_API_KEY"))
index=pc.Index("filingsiq-dev")
embeddings=OpenAIEmbeddings(model="text-embedding-3-small")
co=cohere.ClientV2(api_key=os.getenv("COHERE_API_KEY"))
llm=ChatOpenAI(model="gpt-4o-mini",temperature=0)

#dense retrieval
def dense_retrieve(query:str,top_k:int=3)->list:
    query_embedding=embeddings.embed_query(query)
    results=index.query(
        vector=query_embedding,
        top_k=top_k,
        include_metadata=True
    )
    return [m["metadata"]["text"] for m in results["matches"]]

#HyDE retrieval
HYDE_PROMPT = ChatPromptTemplate.from_template("""
You are a financial analyst. Write a short passage that would appear 
in Apple's SEC 10-K filing and directly answers this question.

IMPORTANT rules:
- You MUST use these exact keywords from the question in your passage: {keywords}
- Use realistic but approximate numbers if needed
- Write 2-3 sentences only
- Do not say "I" or reference the question
- Sound like actual filing language

Question: {question}

Passage:""")

hyde_chain=HYDE_PROMPT|llm|StrOutputParser()

def extract_keywords_bm25(query:str,top_n:int=5)->str:
    tokens=query.lower().replace("?","").split()
    token_scores={}
    for token in set(tokens):
        single_score=bm25.get_scores([token])
        token_scores[token]=float(np.max(single_score))
    top_tokens=sorted(token_scores,key=token_scores.get,reverse=True)[:top_n]
    print(f"  Token scores: {[(t, f'{token_scores[t]:.3f}') for t in top_tokens]}")
    return ", ".join(top_tokens)


def hyde_retrieve(question:str,top_k:int=3)->list:
    keywords=extract_keywords_bm25(question,top_n=5)
    hypothetical_answer=hyde_chain.invoke({"question":question,"keywords":keywords})
    print(f"\n  Hypothetical answer: {hypothetical_answer[:150]}...")

    #embed the hypothetical answer
    hyde_embedding=embeddings.embed_query(hypothetical_answer)

    results=index.query(
        vector=hyde_embedding,
        top_k=top_k,
        include_metadata=True
    )

    return[m["metadata"]["text"] for m in results["matches"]]

questions = [
    "What was Apple's net income in 2025?",
    "What was Apple's total revenue from Services in 2025?",
    "What products did Apple release in Q2 2025?"
]

for q in questions:
    print(f"\n{'='*70}")
    print(f"Query: {q}")
    print(f"{'='*70}")

    print("\n--- STANDARD DENSE RETRIEVAL ---")
    standard_results = dense_retrieve(q, top_k=3)
    for i, chunk in enumerate(standard_results):
        print(f"  [{i+1}] {chunk[:150]}...")

    print("\n--- HyDE RETRIEVAL ---")
    hyde_results = hyde_retrieve(q, top_k=3)
    for i, chunk in enumerate(hyde_results):
        print(f"  [{i+1}] {chunk[:150]}...")
