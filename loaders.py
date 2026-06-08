import os
from dotenv import load_dotenv
from langchain_community.document_loaders import PyPDFLoader,WebBaseLoader
import bs4
load_dotenv()

#pdf loader
loader=PyPDFLoader("/Users/vishnuvardhan/Downloads/AI_Engineer_Roadmap_v4_complete.pdf")
docs=loader.load()

print(f"Number of Pages:{len(docs)}")
print(f"First page content\n{docs[0].page_content[:500]}")
print(f"Metadata: {docs[0].metadata}")

#web based loader
loader=WebBaseLoader(
    web_paths=["https://lilianweng.github.io/posts/2023-06-23-agent/"],
    bs_kwargs={"parse_only":bs4.SoupStrainer(class_=("post-content","post-title","post-header"))}
)

docs=loader.load()

print(f"Number of docs: {len(docs)}")
print(f"Total characters: {len(docs[0].page_content)}")
print(f"Metadata: {docs[0].metadata}")


