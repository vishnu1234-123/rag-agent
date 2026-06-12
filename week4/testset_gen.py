import os
import bs4
import requests
from langchain_core.documents import Document
from dotenv import load_dotenv
from langchain_text_splitters import RecursiveCharacterTextSplitter

from langchain_openai import ChatOpenAI,OpenAIEmbeddings
from ragas.llms import LangchainLLMWrapper
from ragas.embeddings import LangchainEmbeddingsWrapper
from ragas.testset import TestsetGenerator
from ragas.testset.synthesizers.single_hop.specific import SingleHopSpecificQuerySynthesizer
import pandas as pd

load_dotenv()

headers={
    "User-Agent":"rag-agent-research vishnuvardhan1920@gmail.com"
}

url = "https://www.sec.gov/Archives/edgar/data/320193/000032019325000079/aapl-20250927.htm"
response=requests.get(url,headers=headers)
response.raise_for_status()
soup=bs4.BeautifulSoup(response.text,"html.parser")
text=soup.get_text()

docs=[Document(page_content=text,metadata={"source":url})]
text=docs[0].page_content
idx=text.find("PART I")
clean_text=text[idx:]

docs=[Document(page_content=clean_text,meta_data={
    "source":url,
    "company":"Apple",
    "filing_type":"10-K",
    "fiscal_year":"2025"
})]

#split into chunks

splitter=RecursiveCharacterTextSplitter(
    chunk_size=1500,
    chunk_overlap=200,
    add_start_index=True
)
splits=splitter.split_documents(docs)

generator_llm=LangchainLLMWrapper(ChatOpenAI(model="gpt-4o-mini"))
generator_embeddings=LangchainEmbeddingsWrapper(OpenAIEmbeddings(model="text-embedding-3-small"))

generator=TestsetGenerator(llm=generator_llm,embedding_model=generator_embeddings)


query_distribution=[
    (SingleHopSpecificQuerySynthesizer(llm=generator_llm),1.0)
]

print("\nGenerating testset (this may take a few minutes)...")
testset=generator.generate_with_langchain_docs(splits,testset_size=100,query_distribution=query_distribution)

df=testset.to_pandas()
df.to_csv("week4/apple_10k_testset_100.csv", index=False)
print(f"Saved {len(df)} questions to apple_10k_testset_100.csv")
print(f"\nColumns: {df.columns.tolist()}")


