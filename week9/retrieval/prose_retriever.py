import os 
import sqlite3
from pathlib import Path
from dotenv import load_dotenv

_HERE=Path(__file__).resolve()
load_dotenv(_HERE.parent.parent.parent/".env")
load_dotenv()

from openai import OpenAI
from pinecone import Pinecone

import sys
_WEEK8=_HERE.parent.parent.parent/"week8"
sys.path.insert(0,str(_WEEK8))
from config import EMBED_MODEL,INDEX_NAME,NAMESPACE,PARENT_DB,PARENT_PER_QUERY

_oai=OpenAI()
_pc=Pinecone(api_key=os.environ["PINECONE_API_KEY"])
_index=_pc.Index(INDEX_NAME)

def embed_query(text):
    return _oai.embeddings.create(model=EMBED_MODEL,input=[text]).data[0].embedding

def _fetch_parents(parent_ids):
    if not parent_ids:
        return {}
    conn=sqlite3.connect(PARENT_DB)
    try:
        q=",".join("?"*len(parent_ids))
        rows=conn.execute(
            f"""SELECT parent_id,ticker,form,fiscal_year,section_item,
                text FROM parents WHERE parent_id IN ({q})
            """,
            list(parent_ids),
        ).fetchall()
    finally:
        conn.close()
    return {r[0]:{"parent_id":r[0],"ticker":r[1],"form":r[2],
            "fiscal_year":r[3],"section_item":r[4],"text":r[5]}
            for r in rows}

def retrieve(question,tickers=None,top_k=PARENT_PER_QUERY,section_item=None,form=None):
    qvec=embed_query(question)

    flt={}
    if tickers:
        tks=tickers if isinstance(tickers,list) else [tickers]
        flt["ticker"]={"$in":tks} if len(tks)>1 else tks[0]
    
    if section_item:
        flt["section_item"]=section_item
    
    if form:
        flt["form"]=form
    
    res=_index.query(vector=qvec,top_k=top_k,namespace=NAMESPACE,
                    include_metadata=True,filter=flt or None)
    
    children=[]
    order=[]
    child_by_parent={}
    best_score={}

    for m in res["matches"]:
        md=m["metadata"]
        pid=md.get("parent_id")
        children.append({"id": m["id"], "score": m["score"], "parent_id": pid,
                         "ticker": md.get("ticker"), "text": md.get("text")})
        if pid not in child_by_parent:
            order.append(pid)
            child_by_parent[pid]=[]
            best_score[pid]=m["score"]
        child_by_parent[pid].append(m["id"])
    parent_rows=_fetch_parents(order)
    parents=[]
    for pid in order:
        row=parent_rows.get(pid)
        if not row:
            continue
        row=dict(row)
        row["best_score"]=best_score[pid]
        row["child_ids"]=child_by_parent[pid]
        row["n_matched"]=len(child_by_parent[pid])
        parents.append(row)
    parents.sort(key=lambda r:(r["n_matched"],r["best_score"]),reverse=True)

    return {"parents":parents,"children":children,"query":question}

if __name__=="__main__":
    import json

    out=retrieve("What supply chain risks does the company face?",tickers="AAPL",top_k=10)
    print(f"children: {len(out['children'])}  parents: {len(out['parents'])}")
    for p in out["parents"][:3]:
        print(f"  {p['ticker']} {p.get('section_item')} score={p['best_score']:.3f} "
              f"chars={len(p['text'])} children={len(p['child_ids'])}")

        

    
