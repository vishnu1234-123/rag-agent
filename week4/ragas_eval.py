import os
import sys
import bs4
from dotenv import load_dotenv

load_dotenv()
os.environ["USER_AGENT"]            = "rag-agent/1.0"
os.environ["LANGCHAIN_TRACING_V2"]  = os.getenv("LANGCHAIN_TRACING_V2")
os.environ["LANGCHAIN_API_KEY"]     = os.getenv("LANGCHAIN_API_KEY")
os.environ["LANGCHAIN_PROJECT"]     = os.getenv("LANGCHAIN_PROJECT")

from langchain_openai import ChatOpenAI
from ragas import evaluate,EvaluationDataset
from ragas.llms import LangchainLLMWrapper
from ragas.metrics import LLMContextRecall,Faithfulness,FactualCorrectness

from pipelines import VanillaRAG,CRAGPipeline,SelfRAGPipeline,CombinedRAGPipeline


# ── EVAL QUESTIONS + GROUND TRUTHS ────────────────────────────────────────────

eval_questions = [
    "What is task decomposition?",
    "What is the ReAct framework?",
    "What is chain of thought prompting?",
    "What are the three components of an LLM agent?",
    "What is self reflection in LLM agents?",
    "What is the difference between short term and long term memory in agents?",
    "What is Tree of Thoughts?",
    "How do LLM agents use external APIs?",
    "What is MIPS in the context of memory?",
    "What is Generative Agents?"
]

ground_truths = [
    "Task decomposition breaks large tasks into smaller subgoals using Chain of Thought or Tree of Thoughts. LLM+P uses external planner with PDDL for long-horizon planning.",
    "ReAct integrates reasoning and acting by extending action space to combine task-specific discrete actions and language space enabling LLM to interact with environment and generate reasoning traces.",
    "Chain of thought prompting instructs model to think step by step to decompose hard tasks into simpler steps using more test-time computation.",
    "Planning, memory and tool use are the three core components of an LLM powered agent.",
    "Self reflection allows agents to critique and refine past actions and outputs to improve future results through frameworks like Reflexion.",
    "Short term memory is in-context learning restricted by finite context window. Long term memory uses external vector store with fast retrieval for infinite storage.",
    "Tree of Thoughts extends chain of thought by exploring multiple reasoning paths creating a tree structure searched with BFS or DFS.",
    "LLM agents use external APIs for current information, code execution and access to proprietary information sources missing from model weights.",
    "MIPS stands for Maximum Inner Product Search used to save embeddings into vector store database supporting fast retrieval using approximate nearest neighbor algorithms.",
    "Generative Agents is an experiment where 25 virtual characters controlled by LLM-powered agents live and interact in sandbox environment combining memory, planning and reflection."
]


#RAGAS EVALUVATOR

evaluator_llm=LangchainLLMWrapper(ChatOpenAI(model="gpt-4o-mini"))

def run_ragas(pipeline,name:str)->dict:
    "run pipeline on all questions and evaluate with RAGAS"
    print(f"\nRunning {name} on {len(eval_questions)} questions...")

    dataset=[]
    results=pipeline.evaluate(eval_questions)

    for i,results in enumerate(results):
        dataset.append({
            "user_input":results["question"],
            "retrieved_contexts":results["contexts"],
            "response":results["answer"],
            "reference":ground_truths[i]
        })
    evaluation_dataset=EvaluationDataset.from_list(dataset)

    print(f"Running RAGAS eval for {name}...")
    scores=evaluate(
        dataset=evaluation_dataset,
        metrics=[LLMContextRecall(),Faithfulness(),FactualCorrectness()],
        llm=evaluator_llm
    )

    return{
        "name":name,
        "faithfulness":scores["faithfulness"],
        "context_recall":scores["context_recall"],
        "factual_correctness":scores["factual_correctness(mode=f1)"]
    }

#main 

if __name__=="__main__":
    print("Initializing pipelines...")
    vanilla=VanillaRAG()
    crag=CRAGPipeline()
    self_rag=SelfRAGPipeline()
    combined=CombinedRAGPipeline()

    #shared vector store
    crag.vector_store=vanilla.vector_store
    self_rag.vector_store=vanilla.vector_store
    combined.vector_store=vanilla.vector_store

    #run all scores
    all_scores=[]
    all_scores.append(run_ragas(vanilla,"vanilla"))
    all_scores.append(run_ragas(crag,"CRAG"))
    all_scores.append(run_ragas(self_rag,"SelfRAG"))
    all_scores.append(run_ragas(combined,"Combined"))

    #print comparision table
    print("\n" + "="*70)
    print("RAGAS COMPARISON TABLE")
    print("="*70)
    print(f"{'Pipeline':<20} {'Faithfulness':>14} {'Context Recall':>15} {'Factual Correct':>16}")
    print("-"*70)



    for s in all_scores:
        avg_faith   = sum(s['faithfulness']) / len(s['faithfulness'])
        avg_recall  = sum(s['context_recall']) / len(s['context_recall'])
        avg_factual = sum(float(x) for x in s['factual_correctness']) / len(s['factual_correctness'])
        print(f"{s['name']:<20} {avg_faith:>14.2f} {avg_recall:>15.2f} {avg_factual:>16.2f}")

