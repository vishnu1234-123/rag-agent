import os
import sys
import bs4
import requests
import pandas as pd
from dotenv import load_dotenv
from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter

load_dotenv()

os.environ["USER_AGENT"]           = "rag-agent/1.0"
os.environ["LANGCHAIN_TRACING_V2"] = os.getenv("LANGCHAIN_TRACING_V2")
os.environ["LANGCHAIN_API_KEY"]    = os.getenv("LANGCHAIN_API_KEY")
os.environ["LANGCHAIN_PROJECT"]    = os.getenv("LANGCHAIN_PROJECT")

from pipelines import VanillaRAG,CRAGPipeline,SelfRAGPipeline,CombinedRAGPipeline
from ragas import evaluate,EvaluationDataset
from ragas.llms import LangchainLLMWrapper
from ragas.metrics import LLMContextRecall,Faithfulness,FactualCorrectness
from langchain_openai import ChatOpenAI

#build apple 10-k chunks

headers={"User-Agent":"rag-agent-research vishnuvardhan1920@gmail.com"}
url="https://www.sec.gov/Archives/edgar/data/320193/000032019325000079/aapl-20250927.htm"

response=requests.get(url,headers=headers)
response.raise_for_status()

soup=bs4.BeautifulSoup(response.text,"html.parser")
text=soup.get_text()
idx=text.find("PART I")
clean_text=text[idx:]

docs=[Document(page_content=clean_text,meta_data={
    "source":url,
    "company":"Apple",
    "filings_type":"10-K",
    "fiscal_year":"2025"
})]

splitter=RecursiveCharacterTextSplitter(
    chunk_size=1500,
    chunk_overlap=200,
    add_start_index=True
)

apple_splits=splitter.split_documents(docs)
print(f"Apple 10-K split into {len(apple_splits)} chunks")

#load test set

testset=pd.read_csv("week4/apple_10k_testset_clean.csv")

SUBSET_SIZE=20
testset_subset=testset.head(SUBSET_SIZE)
print(f"Running eval on {len(testset_subset)} questions")

#RAGAS Evaluator

evaluator_llm=LangchainLLMWrapper(ChatOpenAI(model="gpt-4o-mini"))

def run_ragas(pipeline,name:str,questions:list,references:list)->dict:
    print(f"\nRunning {name} on {len(questions)} questions...")
    dataset=[]
    for i,q in enumerate(questions):
        result=pipeline.run(q)
        dataset.append({
            "user_input":q,
            "retrieved_contexts":result["contexts"],
            "response":result["answer"],
            "reference":references[i]
        })
    evaluation_dataset=EvaluationDataset.from_list(dataset)

    scores=evaluate(
        dataset=evaluation_dataset,
        metrics=[LLMContextRecall(),Faithfulness(),FactualCorrectness()],
        llm=evaluator_llm
    )

    df=scores.to_pandas()

    return{
        "name":name,
        "faithfulness":df["faithfulness"].mean(),
        "context_recall":df["context_recall"].mean(),
        "factual_correctness": df[[c for c in df.columns if "factual_correctness" in c][0]].mean()
    }

# ── 4. RUN ON ALL 4 PIPELINES ─────────────────────────────────────────────────

if __name__ == "__main__":
    questions  = testset_subset["user_input"].tolist()
    references = testset_subset["reference"].tolist()

    print("Initializing pipelines on Apple 10-K...")
    vanilla  = VanillaRAG(documents=apple_splits,dataset_name="apple_10k")
    crag     = CRAGPipeline(documents=apple_splits,dataset_name="apple_10k")
    self_rag = SelfRAGPipeline(documents=apple_splits,dataset_name="apple_10k")
    combined = CombinedRAGPipeline(documents=apple_splits,dataset_name="apple_10k")

    all_scores = []
    all_scores.append(run_ragas(vanilla,  "VanillaRAG", questions, references))
    all_scores.append(run_ragas(crag,     "CRAG",       questions, references))
    all_scores.append(run_ragas(self_rag, "SelfRAG",    questions, references))
    all_scores.append(run_ragas(combined, "Combined",   questions, references))

    print("\n" + "="*70)
    print("APPLE 10-K RAGAS COMPARISON")
    print("="*70)
    print(f"{'Pipeline':<20} {'Faithfulness':>14} {'Context Recall':>15} {'Factual Correct':>16}")
    print("-"*70)
    for s in all_scores:
        print(f"{s['name']:<20} {s['faithfulness']:>14.2f} {s['context_recall']:>15.2f} {s['factual_correctness']:>16.2f}")