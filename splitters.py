import os
from dotenv import load_dotenv
from langchain_openai import OpenAIEmbeddings
from langchain_experimental.text_splitter import SemanticChunker
from langchain_community.document_loaders import PyPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter,CharacterTextSplitter,TokenTextSplitter

load_dotenv()

#pdf loader
loader=PyPDFLoader("/Users/vishnuvardhan/Downloads/AI_Engineer_Roadmap_v4_complete.pdf")
docs=loader.load()

#splitter 1 - recursive character
recursive_splitter=RecursiveCharacterTextSplitter(
    chunk_size=1000,
    chunk_overlap=0,
)
recursive_splits=recursive_splitter.split_documents(docs)


#splitter 2 - character

character_splitter=CharacterTextSplitter(
    chunk_size=1000,
    chunk_overlap=0,
    separator="\n"
)
character_splits=character_splitter.split_documents(docs)

"""
print(f"Recursive splits: {len(recursive_splits)}")
print(f"Character splits: {len(character_splits)}")
print(f"\nRecursive first chunk: '{recursive_splits[0]}'")
print(f"Character first chunk: '{character_splits[0]}'")
"""

#splitter 3 - token

token_splitter=TokenTextSplitter(
    chunk_size=200,
    chunk_overlap=20,
)

token_splits = token_splitter.split_documents(docs)
"""
print(f"Token splits: {len(token_splits)}")
print(f"\nFirst chunk: {token_splits[0].page_content[:200]}")
print(f"First chunk token count: {len(token_splits[0].page_content.split())}")
"""

#splitter 4 - sematic text splitter

embeddings=OpenAIEmbeddings(model="text-embedding-3-small")

semantic_splitter=SemanticChunker(
    embeddings=embeddings,
    breakpoint_threshold_type="percentile",
    breakpoint_threshold_amount=95
)
semantic_splits = semantic_splitter.split_documents(docs)
print(f"Semantic splits: {len(semantic_splits)}")
print(f"\nFirst chunk:\n{semantic_splits[0].page_content[:300]}")
print(f"\nSecond chunk:\n{semantic_splits[1].page_content[:300]}")