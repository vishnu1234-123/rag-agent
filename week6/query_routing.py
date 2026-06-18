import os
import sys
from typing import Annotated, TypedDict
import numpy as np
import requests
import bs4
import cohere
import time
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI,OpenAIEmbeddings
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter
from pinecone import Pinecone
from rank_bm25 import BM25Okapi
import re
from langchain_tavily import TavilySearch
from pydantic import BaseModel,Field
from langgraph.graph import StateGraph,END
import operator



load_dotenv()

#load chunks
print("Loading Apple 10-K...")
headers={"User-Agent":"rag-agent-research vishnuvardhan1920@gmail.com"}
url = "https://www.sec.gov/Archives/edgar/data/320193/000032019325000079/aapl-20250927.htm"
response=requests.get(url,headers=headers)
soup=bs4.BeautifulSoup(response.text,"html.parser")
text=soup.get_text()
clean_text=text[text.find("PART I"):]
docs=[Document(page_content=clean_text)]
splits=RecursiveCharacterTextSplitter(chunk_size=1500,chunk_overlap=200).split_documents(docs)
texts=[doc.page_content for doc in splits]
print(f"loaded {len(texts)} chunks ")

#setup

tokenized=[t.lower().split() for t in texts]
bm25=BM25Okapi(tokenized)
co=cohere.ClientV2(api_key=os.getenv("COHERE_API_KEY"))
pc=Pinecone(api_key=os.getenv("PINECONE_API_KEY"))
index=pc.Index("filingsiq-dev")
embeddings=OpenAIEmbeddings(model="text-embedding-3-small")
llm=ChatOpenAI(model="gpt-4o-mini",temperature=0)

#pydantic 

class MetricValue(BaseModel):
    metric:str|None=Field(None,description="What was measured:net_income,revenue,gross_margin,etc.")
    value:float|None=Field(None,description="The numerical value")
    year:int|None=Field(None,description="Fiscal year this value refers to")
    unit:str|None=Field(None,description="Unit:millions,billions,percent,etc.")

class FinancialAnswer(BaseModel):
    answer:str=Field(description="Full answer in plain English")
    values:list[MetricValue]=Field(default_factory=list,description="List of all numerical values extracted. Empty list if no numbers.")
    confidence:str=Field(description="high/medium/low based on context clarity")
    source_section:str|None=Field(None,description="10-K section this came from,or null")

structured_llm=llm.with_structured_output(FinancialAnswer)

#prompts

DECOMPOSE_PROMPT=ChatPromptTemplate.from_template("""
You are a financial expert at breaking down complex questions about SEC 
filings into simple focused sub-questions that can each be answeres by searching a 
single document section.
                                                  
Break this question into 2-4 specific sub-questions.
Return ONLY sub-questions,one per line,no numbering or bullets.
Each sub-question should be self-contained and searchable.
                                                  
Question:{question}
Sub-questions:
""")

HYDE_PROMPT = ChatPromptTemplate.from_template("""
You are a financial analyst. Write a short passage that would appear
in Apple's SEC 10-K filing and directly answers this question.

IMPORTANT: You MUST use these exact keywords: {keywords}
Write 2-3 sentences only. Sound like actual filing language.
Do not say "I" or reference the question.

Question: {question}

Passage:""")

GENERATE_PROMPT = ChatPromptTemplate.from_template("""
You are an expert analyst answering questions about Apple's SEC filings.
Use ONLY the provided context to answer the question.
If the context does not contain enough information, say so explicitly.

Context:
{context}

Question: {question}

Answer:""")

CHECK_PROMPT = ChatPromptTemplate.from_template("""
Does this question require information from MULTIPLE sections,
time periods, or metrics to answer completely?

Return ONLY the word True or False, nothing else.

Question: {question}
Answer:""")

CLASSIFY_PROMPT=ChatPromptTemplate.from_template("""
You are a query router for a RAG system over Apple's SEC 10-K filing.

Classify the query into exactly one of these categories:
-DIRECT: can be answered by LLM without any document retrieval
(math calculations,general knowledge definitions)
-WEB: requires current information not in the filing
(todays's stock price,recent news,competitor data,
information about other companies not mentioned in the filing)
-KEYWORD: requires finding specific facts,numbers,dates,or named 
enitites in the filing (net income,product releases,specific financial figures)
-CONCEPTUAL:requires understanding broad themes or startergies in the filing
(risk stratergy,competetive positioning,business model explanation)
IMPORTANT: Product releases,financial results, and events from FY2025(before September 27,2025) ARE
in the filing-classify these as KEYWORD,not WEB.
RETURN ONLY WORD: DIRECT,WEB,KEYWORD OR CONCEPTUAL
                    
Query:{query}
""")

STRUCTURED_PROMPT = ChatPromptTemplate.from_template("""
You are an expert analyst answering questions about Apple's SEC filings.
Use ONLY the provided context to answer the question.
Extract any numerical values, units, years, and metrics precisely.
If a field is not applicable, return null.

Context:
{context}

Question: {question}""")


decompose_chain = DECOMPOSE_PROMPT | llm | StrOutputParser()
hyde_chain      = HYDE_PROMPT      | llm | StrOutputParser()
generate_chain  = GENERATE_PROMPT  | llm | StrOutputParser()
check_chain     = CHECK_PROMPT     | llm | StrOutputParser()
classify_chain  = CLASSIFY_PROMPT  | llm | StrOutputParser()
structured_chain = STRUCTURED_PROMPT | structured_llm




#retrieval helpers

def reciprocal_rank_fusion(query:str,top_k:int=10)->list:
    query_embedding=embeddings.embed_query(query)
    dense_results=index.query(
        vector=query_embedding,
        top_k=len(texts),
        include_metadata=True
    )

    dense_ranking={int(m["id"].split("-")[-1]):rank+1
        for rank,m in enumerate(dense_results["matches"])
    }

    bm25_scores=bm25.get_scores(query.lower().split())
    bm25_ranking={int(idx):rank+1
        for rank,idx in enumerate(np.argsort(bm25_scores)[::-1])
    }

    rrf_scores={
        i:1/(60+dense_ranking.get(i,len(texts)))+1/(60+bm25_ranking.get(i,len(texts)))
        for i in range(len(texts))
    }

    top_indices=sorted(rrf_scores,key=rrf_scores.get,reverse=True)[:top_k]
    return [texts[i] for i in top_indices]

def retrieve_and_rerank(query:str,top_k:int=3)->list:
    time.sleep(7)
    candidates=reciprocal_rank_fusion(query,top_k=10)
    reranked=co.rerank(
        query=query,
        documents=candidates,
        top_n=top_k,
        model="rerank-english-v3.0"
    )
    return [candidates[r.index] for r in reranked.results]

def extract_keywords_bm25(query:str,top_n:int=5)->str:
    tokens=query.lower().replace("?","").split()
    token_scores={}
    for token in tokens:
        single_score=bm25.get_scores([token])
        token_scores[token]=float(np.max(single_score))
    top_token=sorted(token_scores,key=token_scores.get,reverse=True)[:top_n]
    return ", ".join(top_token)

def hyde_retrieve(question:str,top_k:int=3)->list:
    keywords=extract_keywords_bm25(question)
    hypothetical_answer=hyde_chain.invoke({"question":question,"keywords":keywords})
    print(f"  [HyDE] hypothetical: {hypothetical_answer[:150]}...")
    hyde_embedding=embeddings.embed_query(hypothetical_answer)
    results=index.query(
        vector=hyde_embedding,
        top_k=top_k,
        include_metadata=True
    )

    return [m["metadata"]["text"] for m in results["matches"]]

#routing logic
def needs_decomposition(query:str)->bool:
    explicit_indicators = [
        "compare", "vs", "versus", "difference between",
        "change from", "how did", "both", "across",
        "over the years", "trend"
    ]
    implicit_indicators = [
        "journey", "history", "evolution", "lately", "recent",
        "over time", "past", "years", "growth", "decline",
        "what drove", "why did", "how has", "performance"
    ]

    years_mentioned=re.findall(r'\b20\d{2}\b',query)

    has_explicit=any(ind in query.lower() for ind in explicit_indicators)
    has_implicit=any(ind in query.lower() for ind in implicit_indicators)
    has_multiple_layers=len(set(years_mentioned))>1
    is_long=len(query.split())>12

    if not any([has_explicit,has_implicit,has_multiple_layers,is_long]):
        return False
    
    result=check_chain.invoke({"question":query})
    decision=result.lower().startswith("true")
    print(f"  [ROUTER] decomposition={decision} (LLM verified)")
    return decision

def classify_query(query:str)->str:
    result=classify_chain.invoke({"query":query}).strip().upper()
    valid={"DIRECT","WEB","KEYWORD","CONCEPTUAL"}
    route=result if result in valid else "KEYWORD"
    print(f"[CLASSIFIER] -> {route}")
    return route
"""
def decompose_rag(question:str)->dict:
    result=decompose_chain.invoke({"question":question})
    sub_queries=[q.strip() for q in result.strip().split("\n") if q.strip()]
    print(f"  [DECOMPOSE] {len(sub_queries)} sub-queries:")
    for i,q in enumerate(sub_queries):
        print(f"{i+1}. {q}")

    all_contexts=[]
    seen=set()
    for sub_q in sub_queries:
        chunks=retrieve_and_rerank(sub_q,top_k=2)
        for chunk in chunks:
            all_contexts.append(chunk)
            seen.add(chunk)
    
    print(f"  [DECOMPOSE] {len(all_contexts)} unique chunks retrieved")
    answer = generate_chain.invoke({
        "context": "\n\n---\n\n".join(all_contexts),
        "question": question
    })
    return {"question": question, "answer": answer,
            "route": "decomposition", "num_contexts": len(all_contexts)}
"""
tavily=TavilySearch(max_results=3)

def web_search_retrieve(query:str)->list:
    print(f"[WEB SEARCH] searching: {query}")
    results=tavily.invoke(query)
    raw_list=[]
    if isinstance(results,list):
        raw_list=results
    elif isinstance(results,dict):
        raw_list=results.get("results",[])

    if not isinstance(results,list):
        results=[]
    extracted_contexts=[]
    for r in raw_list:
        if isinstance(r, dict):
            # Check 'content' first, fallback to 'snippet' if 'content' is missing
            text = r.get("content") or r.get("snippet") or r.get("raw_content")
            if text:
                extracted_contexts.append(text.strip())
                
    return extracted_contexts


class DecompositionState(TypedDict):
    question:str
    sub_queries:list[str]
    contexts:Annotated[list[str],operator.add]
    answer:str

#langgraph nodes
def decompose_node(state:DecompositionState)->dict:
    result=decompose_chain.invoke({"question":state["question"]})
    sub_queries=[q.strip() for q in result.strip().split("\n") if q.strip()]
    print(f"[DECOMPOSE] {len(sub_queries)} sub-queries")

    for i,q in enumerate(sub_queries):
        print(f"{i+1}.{q}")
    return {"sub_queries":sub_queries,"contexts":[]}

def make_retrieve_node(sub_query_idx:int):
    def retrieve_node(state:DecompositionState)->dict:
        if sub_query_idx>=len(state["sub_queries"]):
            return {"contexts":[]}
        sub_q=state["sub_queries"][sub_query_idx]
        print(f"[RETRIEVE {sub_query_idx+1}].{sub_q[:60]}...")
        chunks=retrieve_and_rerank(sub_q,top_k=2)
        return {"contexts":chunks}
    return retrieve_node

def generate_node(state:DecompositionState)->dict:
    seen=set()
    unique_contexts=[]
    for chunk in state["contexts"]:
        if chunk not in seen:
            seen.add(chunk)
            unique_contexts.append(chunk)
    
    print(f"[GENERATE] {len(unique_contexts)} unique chunks")

    answer=generate_chain.invoke({
        "context":"\n\n---\n\n".join(unique_contexts),
        "question":state["question"]
    })
    return {"answer":answer}

#build langgraph

def build_parllel_graph(max_sub_queries:int=4):
    graph=StateGraph(DecompositionState)

    #add nodes
    graph.add_node("decompose",decompose_node)
    for i in range(max_sub_queries):
        graph.add_node(f"retrieve_{i}",make_retrieve_node(i))
    graph.add_node("generate",generate_node)

    #add edges
    graph.set_entry_point("decompose")
    for i in range(max_sub_queries):
        graph.add_edge("decompose",f"retrieve_{i}")
    
    for i in range(max_sub_queries):
        graph.add_edge(f"retrieve_{i}","generate")
    graph.add_edge("generate",END)

    return graph.compile()


#main router

def smart_rag(question:str)->dict:
    print(f"\n{'='*70}")
    print(f"Query:{question}")

    #decomposition check
    if needs_decomposition(question):
        print("[ROUTER]->[DECOMPOSITION]")
        parllel_app=build_parllel_graph(max_sub_queries=4)
        parllel_app.invoke({"question":question,"sub_queries":[],"contexts":[],"answer":""})

    
    query_type=classify_query(question)

    if query_type=="DIRECT":
        print("[ROUTER]->DIRECT LLM")
        answer=llm.invoke(question).content
        return{"question":question,"answer":answer,"route":"direct_llm","contexts":[]}
    elif query_type=="WEB":
        print("[ROUTER]->[WEB SEARCH (TAVILY)]")
        contexts=web_search_retrieve(question)
    elif query_type=="KEYWORD":
        print("[ROUTER]->[RRF HYBRID+RERANK]")
        contexts=retrieve_and_rerank(question,top_k=3)
    else:
        print("[ROUTER]->[HYDE+DENSE]")
        contexts=hyde_retrieve(question,top_k=3)

    structured_answer = structured_chain.invoke({
    "context": "\n\n---\n\n".join(contexts),
    "question": question
    })

    return {
        "question":       question,
        "route":          query_type,
        "answer":         structured_answer.answer,
        "values":         structured_answer.values,
        "confidence":     structured_answer.confidence,
        "source_section": structured_answer.source_section,
        "contexts":       contexts
    }   
# ── 7. test ───────────────────────────────────────────────────────────────
test_queries = [
    "How did Apple's revenue and net income change from 2023 to 2025?",
    "What was Apple's net income in 2025?",
    "What are Apple's main strategies for competing in global markets?",
    "What is 15% of Apple's $112 billion net income in 2025?",
    "What products did Apple release in Q2 2025?",
]

for q in test_queries:
    result = smart_rag(q)
    print(f"\nROUTE:      {result['route']}")
    print(f"ANSWER:     {result['answer'][:200]}")
    print(f"VALUES:     {result.get('values')}")
    print(f"CONFIDENCE: {result.get('confidence')}")
    print(f"SOURCE:     {result.get('source_section')}")

    
    