import os 
from dotenv import load_dotenv
from pinecone import Pinecone
from langchain_openai import OpenAIEmbeddings

load_dotenv()

pc=Pinecone(api_key=os.getenv("PINECONE_API_KEY"))
index=pc.Index("filingsiq-dev")
embeddings=OpenAIEmbeddings(model="text-embedding-3-small")

def query_pinecone(question:str,top_k:int=3)->list:
    query_embedding=embeddings.embed_query(question)
    results=index.query(
        vector=query_embedding,
        top_k=top_k,
        include_metadata=True
    )
    return results["matches"]

questions = [
    "What was Apple's net income in 2025?",
    "What are Apple's main risk factors?",
    "What products did Apple release in Q2 2025?"
]

for q in questions:
    print(f"\n Question:{q}")
    print("-"*60)
    matches=query_pinecone(q)
    for i,match in enumerate(matches):
        print(f"[{i+1}] score={match["score"]:.3f}")
        print(f"{match["metadata"]["text"][:150]}...")
