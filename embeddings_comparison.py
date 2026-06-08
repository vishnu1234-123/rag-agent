import os 
import bs4
import time
from dotenv import load_dotenv

from langchain_community.vectorstores import FAISS
from langchain_community.document_loaders import WebBaseLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_openai import OpenAIEmbeddings
from langchain_community.embeddings import HuggingFaceEmbeddings

load_dotenv()

# load and split

loader=WebBaseLoader(
    web_paths=["https://lilianweng.github.io/posts/2023-06-23-agent/"],
    bs_kwargs={
        "parse_only":bs4.SoupStrainer(
            class_=("post-content","post-title","post-header")
        )
    }
)

docs=loader.load()
splitter=RecursiveCharacterTextSplitter(
    chunk_size=1000,
    chunk_overlap=200
)
splits=splitter.split_documents(docs)

#open ai embeddings
print("Building OpenAI index...")
start=time.time()
openai_embeddings=OpenAIEmbeddings(model="text-embedding-3-small")
openai_store=FAISS.from_documents(splits,openai_embeddings)
openai_time=time.time()-start
print(f"OpenAI index built in {openai_time:.2f}s")


#bge embeddings 

print("\nBuilding BGE index...")
start=time.time()
bge_embeddings=HuggingFaceEmbeddings(
    model_name="BAAI/bge-base-en-v1.5",
    model_kwargs={"device":"mps"},
    encode_kwargs={"normalize_embeddings":True}
)

bge_store=FAISS.from_documents(splits,bge_embeddings)
bge_time=time.time()-start
print(f"BGE index built in {bge_time:.2f}s")


#compare results
queries = [
    "what is task decomposition?",
    "what is chain of thought prompting?",
    "what tools can LLM agents use?"
]

for query in queries:
    print(f"\n{'='*60}")
    print(f"Query: {query}")
    
    print("\n--- OpenAI ---")
    openai_results = openai_store.similarity_search(query, k=2)
    for i, doc in enumerate(openai_results):
        print(f"Result {i+1}: {doc.page_content[:150]}")

    print("\n--- BGE ---")
    bge_results = bge_store.similarity_search(query, k=2)
    for i, doc in enumerate(bge_results):
        print(f"Result {i+1}: {doc.page_content[:150]}")

#cost comparision
print(f"\n{'='*60}")
print("COMPARISON SUMMARY")
print(f"{'='*60}")
print(f"OpenAI text-embedding-3-small:")
print(f"  Cost:    ~$0.00002 per 1000 tokens")
print(f"  Speed:   {openai_time:.2f}s for {len(splits)} chunks")
print(f"  Dims:    1536")
print(f"  Needs:   API key, internet, costs money")

print(f"\nBGE-small-en-v1.5:")
print(f"  Cost:    FREE (runs locally)")
print(f"  Speed:   {bge_time:.2f}s for {len(splits)} chunks")
print(f"  Dims:    768")
print(f"  Needs:   Nothing, runs on CPU")