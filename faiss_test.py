import os
from dotenv import load_dotenv
from langchain_community.vectorstores import FAISS
from langchain_community.document_loaders import WebBaseLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_openai import OpenAIEmbeddings
import bs4

load_dotenv()

# 1. load
loader = WebBaseLoader(
    web_paths=["https://lilianweng.github.io/posts/2023-06-23-agent/"],
    bs_kwargs={"parse_only": bs4.SoupStrainer(
        class_=("post-content", "post-title", "post-header")
    )}
)
docs = loader.load()

# 2. split
splitter = RecursiveCharacterTextSplitter(
    chunk_size=1000,
    chunk_overlap=200,
)
splits = splitter.split_documents(docs)

# 3. embed + store in FAISS
embeddings = OpenAIEmbeddings(model="text-embedding-3-small")
vector_store = FAISS.from_documents(splits, embeddings)

print(f"Indexed {len(splits)} chunks into FAISS")

# 4. similarity search
query = "what is task decomposition?"
results = vector_store.similarity_search(query, k=3)

print(f"\nTop 3 results for: '{query}'")
for i, doc in enumerate(results):
    print(f"\nResult {i+1}:")
    print(f"Content: {doc.page_content[:200]}")
    print(f"Metadata: {doc.metadata}")

# 5. save to disk
vector_store.save_local("faiss_index")
print("\nSaved FAISS index to disk")

# 6. load back
vector_store_loaded = FAISS.load_local(
    "faiss_index", 
    embeddings,
    allow_dangerous_deserialization=True  # required by langchain for safety
)
print("Loaded FAISS index from disk")

# 7. verify loaded index works
results2 = vector_store_loaded.similarity_search(query, k=1)
print(f"\nLoaded index result: {results2[0].page_content[:200]}")