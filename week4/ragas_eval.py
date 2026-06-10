import os
import bs4
from dotenv import load_dotenv

load_dotenv()
os.environ["USER_AGENT"]            = "rag-agent/1.0"
os.environ["LANGCHAIN_TRACING_V2"]  = os.getenv("LANGCHAIN_TRACING_V2")
os.environ["LANGCHAIN_API_KEY"]     = os.getenv("LANGCHAIN_API_KEY")
os.environ["LANGCHAIN_PROJECT"]     = os.getenv("LANGCHAIN_PROJECT")

from langchain_openai import ChatOpenAI,OpenAIEmbeddings
from langchain_community.vectorstores import FAISS
from langchain_community.document_loaders import WebBaseLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_core.prompts import ChatPromptTemplate

from ragas import evaluate,EvaluationDataset
from ragas.llms import LangchainLLMWrapper
from ragas.metrics import LLMContextRecall,Faithfulness,FactualCorrectness

evaluator_llm=LangchainLLMWrapper(ChatOpenAI(model="gpt-4o-mini"))


# ── 1. INDEX ──────────────────────────────────────────────────────────────────

def build_index():
    loader = WebBaseLoader(
        web_paths=["https://lilianweng.github.io/posts/2023-06-23-agent/"],
        bs_kwargs={"parse_only": bs4.SoupStrainer(
            class_=("post-content", "post-title", "post-header")
        )}
    )
    docs = loader.load()
    
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=1000,
        chunk_overlap=200
    )
    splits = splitter.split_documents(docs)
    
    embeddings = OpenAIEmbeddings(model="text-embedding-3-small")
    vector_store = FAISS.from_documents(splits, embeddings)
    
    print(f"Indexed {len(splits)} chunks")
    return vector_store

vector_store = build_index()
llm = ChatOpenAI(model="gpt-4o-mini", temperature=0)

# ── 2. VANILLA RAG PIPELINE ───────────────────────────────────────────────────

generate_prompt = ChatPromptTemplate.from_messages([
    ("system", """You are an assistant for question-answering tasks.
     Use the following context to answer the question.
     If you don't know say you don't know.
     Keep answer concise and grounded in context."""),
    ("human", "Context:\n{context}\n\nQuestion:\n{question}")
])

generator = generate_prompt | llm

def vanilla_rag(query: str) -> dict:
    """simple vanilla RAG - retrieve and generate"""
    docs    = vector_store.similarity_search(query, k=3)
    context = "\n\n".join([doc.page_content for doc in docs])
    result  = generator.invoke({"context": context, "question": query})
    
    return {
        "question" : query,
        "answer"   : result.content,
        "contexts" : [doc.page_content for doc in docs],
    }

print("Vanilla RAG pipeline ready")

# ── 3. EVAL QUESTIONS ─────────────────────────────────────────────────────────

eval_questions = [
    "What is task decomposition?",
    "What is the ReAct framework?",
    "What is chain of thought prompting?",
]

ground_truths = [
    "Task decomposition breaks large tasks into smaller subgoals using Chain of Thought or Tree of Thoughts. LLM+P uses external planner with PDDL for long-horizon planning.",
    "ReAct integrates reasoning and acting by extending action space to combine task-specific discrete actions and language space enabling LLM to interact with environment and generate reasoning traces.",
    "Chain of thought prompting instructs model to think step by step to decompose hard tasks into simpler steps using more test-time computation.",
]



# ── 5. RAGAS EVALUATION ───────────────────────────────────────────────────────

dataset=[]
for i,q in enumerate(eval_questions):
    result=vanilla_rag(q)
    dataset.append(
        {
            "user_input":result["question"],
            "retrieved_contexts":result["contexts"],
            "response":result["answer"],
            "reference":ground_truths[i]
        }
    )

evaluation_dataset=EvaluationDataset.from_list(dataset)

scores=evaluate(
    dataset=evaluation_dataset,
    metrics=[
        Faithfulness(),
        LLMContextRecall(),
        FactualCorrectness()
    ],
    llm=evaluator_llm,
)

print(scores)