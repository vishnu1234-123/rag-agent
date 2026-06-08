import os
import bs4
from dotenv import load_dotenv

from langchain_community.vectorstores import FAISS
from langchain_community.document_loaders import WebBaseLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_openai import OpenAIEmbeddings,ChatOpenAI
from langchain_classic.retrievers.document_compressors import DocumentCompressorPipeline
from langchain_classic.retrievers import ContextualCompressionRetriever
from langchain_classic.retrievers.document_compressors import LLMChainExtractor
from langchain_community.document_transformers import EmbeddingsRedundantFilter
load_dotenv()

EMBED_MODEL = "text-embedding-3-small"

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

# 3. FAISS index
embeddings = OpenAIEmbeddings(model=EMBED_MODEL)
vector_store = FAISS.from_documents(splits, embeddings)

print(f"Indexed {len(splits)} chunks")
print("Ready to test retrievers...")

# 4. similarity search vs mmr
query="what is task decomposition?"

#regular similarity search
similarity_results=vector_store.similarity_search(
    query,
    k=3
)

#mmr search
mmr_results=vector_store.max_marginal_relevance_search(
    query,
    k=3,
    fetch_k=30
)

print("\n--- SIMILARITY SEARCH ---")
for i,doc in enumerate(similarity_results):
    print(f"\nResult {i+1}:\n{doc.page_content[:200]}")

print("\n--- MMR SEARCH ---")
for i, doc in enumerate(mmr_results):
    print(f"\nResult {i+1}:\n{doc.page_content[:200]}")


# 5. CONTEXTUAL COMPRESSION

base_retriever=vector_store.as_retriever(search_kwargs={"k":3})

llm=ChatOpenAI(model="gpt-4o-mini",temperature=0)
compressor=LLMChainExtractor.from_llm(llm)

compressor_retriever=ContextualCompressionRetriever(
    base_compressor=compressor,
    base_retriever=base_retriever
)

query="what is task decomposition?"
compressed_results=compressor_retriever.invoke(query)

print("\n--- CONTEXTUAL COMPRESSION ---")
for i, doc in enumerate(compressed_results):
    print(f"\nResult {i+1} ({len(doc.page_content)} chars):\n{doc.page_content}")

# add embedding redundant filter

base_retriever=vector_store.as_retriever(search_type="mmr",search_kwargs={"k":3,"fetch_k":15})

redundant_filter=EmbeddingsRedundantFilter(embeddings=embeddings,similarity_threshold=0.95)
compressor_pipeline=DocumentCompressorPipeline(transformers=[redundant_filter])
redundant_retriever=ContextualCompressionRetriever(
    base_compressor=compressor_pipeline,
    base_retriever=base_retriever
)

query = "what is task decomposition?"

print("\n--- REGULAR SIMILARITY (k=3) ---")
regular_results = base_retriever.invoke(query)
for i, doc in enumerate(regular_results):
    print(f"\nResult {i+1} ({len(doc.page_content)} chars):\n{doc.page_content[:200]}")

print("\n--- REDUNDANT FILTER ---")
filtered_results = redundant_retriever.invoke(query)
print(f"Returned {len(filtered_results)} docs after filtering")
for i, doc in enumerate(filtered_results):
    print(f"\nResult {i+1} ({len(doc.page_content)} chars):\n{doc.page_content[:200]}")



