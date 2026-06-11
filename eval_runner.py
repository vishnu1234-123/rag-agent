import json 
import bs4
from dotenv import load_dotenv

from langchain_community.vectorstores import FAISS
from langchain_community.document_loaders import WebBaseLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_openai import OpenAIEmbeddings

load_dotenv()

# load and split
loader=WebBaseLoader(
    web_paths=["https://lilianweng.github.io/posts/2023-06-23-agent/"],
    bs_kwargs={"parse_only": bs4.SoupStrainer(
        class_=("post-content", "post-title", "post-header")
    )}
)

docs=loader.load()

splitter=RecursiveCharacterTextSplitter(
    chunk_size=1000,
    chunk_overlap=200
)
splits=splitter.split_documents(docs)

embeddings=OpenAIEmbeddings(model="text-embedding-3-small")
vector_store=FAISS.from_documents(splits,embeddings)

#load eval set
with open('eval_set.json') as f:
    eval_set=json.load(f)

#eval function

def check_hit(results,keywords):
    combined =" ".join([doc.page_content.lower() for doc in results])
    hits=[kw.lower() in combined for kw in keywords]
    return sum(hits)/len(hits)

#run eval 

print(f"\n{'ID':<4} {'Question':<45} {'Similarity':>10} {'MMR':>8}")
print("-" * 72)

similarity_scores=[]
mmr_scores=[]

for item in eval_set:
    question=item["question"]
    keywords=item["expected_keywords"]

    #similarity
    sim_results=vector_store.similarity_search(question,k=3)
    sim_score=check_hit(sim_results,keywords)

    #mmr
    mmr_results=vector_store.max_marginal_relevance_search(
        question,k=3,fetch_k=15
    )
    mmr_score=check_hit(mmr_results,keywords)

    similarity_scores.append(sim_score)
    mmr_scores.append(mmr_score)

    print(f"{item['id']:<4} {question[:44]:<45} {sim_score:>10.2f} {mmr_score:>8.2f}")
   
avg_sim = sum(similarity_scores) / len(similarity_scores)
avg_mmr = sum(mmr_scores) / len(mmr_scores)

print("-" * 72)
print(f"{'AVERAGE':<49} {avg_sim:>10.2f} {avg_mmr:>8.2f}")
print(f"\nWinner: {'Similarity' if avg_sim > avg_mmr else 'MMR' if avg_mmr > avg_sim else 'Tie'}")




