"""
STAGE 2 — Embed prose children and upsert to Pinecone.

Safety properties:
  no duplicates on re-run   -> deterministic IDs (upsert overwrites)
  no wasted API calls       -> content_hash vs manifest
  resumable after a crash   -> manifest saved AFTER each confirmed upsert
  one bad chunk can't halt  -> dead-letter list, run continues
  no silent data loss       -> count assertion in validate.py

    python embed_and_upsert.py
"""

from __future__ import annotations

import json
import os 
import sqlite3
import sys
import time
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent.parent/".env")
load_dotenv()

from openai import OpenAI
from pinecone import Pinecone,ServerlessSpec
from tenacity import retry,stop_after_attempt,wait_exponential

from chunk_loader import load_chunks
from build_parents import build_parents
from config import(EMBED_BATCH_SIZE,EMBED_DIM,EMBED_MODEL,INDEX_CLOUD,
                   INDEX_METRIC,INDEX_NAME,INDEX_REGION,MANIFEST,
                   NAMESPACE,PARENT_DB)

DEAD_LETTER=MANIFEST.parent/"dead_letter.json"

openai_client=OpenAI()

pc=Pinecone(api_key=os.environ["PINECONE_API_KEY"])

def ensure_index():
    existing=[i["name"] for i in pc.list_indexes()]
    if INDEX_NAME not in existing:
        print(f"creating index {INDEX_NAME} (metric={INDEX_METRIC})")
        pc.create_index(
            name=INDEX_NAME,dimension=EMBED_DIM,metric=INDEX_METRIC,
            spec=ServerlessSpec(cloud=INDEX_CLOUD,region=INDEX_REGION)
        )
        while not pc.describe_index(INDEX_NAME).status["ready"]:
            time.sleep(0.2)
        print("index ready")
    else:
        desc=pc.describe_index(INDEX_NAME)
        if desc.metric!=INDEX_METRIC:
            sys.exit(f"FATAL: index '{INDEX_NAME}' has metric '{desc.metric}',"
                     f"config wants '{INDEX_METRIC}'.Delete and recreate.")
    return pc.Index(INDEX_NAME)

    

def load_manifest():
    if MANIFEST.exists():
        return json.loads(MANIFEST.read_text())
    return {}

def save_manifest(m:dict):
    MANIFEST.parent.mkdir(parents=True,exist_ok=True)
    tmp=MANIFEST.with_suffix(".tmp")
    tmp.write_text(json.dumps(m))
    tmp.replace(MANIFEST)

@retry(stop=stop_after_attempt(5),
       wait=wait_exponential(multiplier=2,min=2,max=60),reraise=True)
def embed_batch(texts:list[str])->list[list[float]]:
    resp=openai_client.embeddings.create(model=EMBED_MODEL,input=texts)
    return [d.embedding for d in resp.data]

def main():
    children=load_chunks()
    _,children_to_parent=build_parents(children)
    print(f"prose children: {len(children)}")

    conn=sqlite3.connect(PARENT_DB)
    parent_ids={r[0] for r in conn.execute("SELECT parent_id FROM parents")}
    conn.close()

    orphans=[c.id for c in children if children_to_parent.get(c.id) not in parent_ids]
    if orphans:
        sys.exit(f"FATAL: {len(orphans)} children map to missing parents."
                 f"Rebuild parents first.")
    
    index=ensure_index()
    manifest=load_manifest()
    dead_letter:list[dict]=[]
    embedded=skipped=0
    total_batches=(len(children)+EMBED_BATCH_SIZE-1)//EMBED_BATCH_SIZE

    for bnum,start in enumerate(range(0,len(children),EMBED_BATCH_SIZE),1):
        batch=children[start:start+EMBED_BATCH_SIZE]
        todo=[c for c in batch if manifest.get(c.id)!=c.content_hash]
        skipped+=len(batch)-len(todo)
        if not todo:
            continue

        try:
            values=embed_batch([c.text for c in todo])
        except Exception as exc:
            print(f"batch {bnum} failed:{exc}")
            dead_letter.extend({"id":c.id,"error":str(exc)} for c in todo)
            continue
        vectors=[]
        for c,v in zip(todo,values):
            md={
                "ticker":c.ticker,"form":c.form,
                "parent_id":children_to_parent[c.id],
                "content_hash":c.content_hash,
                "embedding_model":EMBED_MODEL,
                "text":c.text,
            }

            if c.section_item:
                md["section_item"]=c.section_item
            if c.n_tokens is not None:
                md["n_tokens"]=c.n_tokens
            vectors.append({"id":c.id,"values":v,"metadata":md})
        index.upsert(vectors=vectors,namespace=NAMESPACE)

        for c in todo:
            manifest[c.id]=c.content_hash
        save_manifest(manifest)

        embedded+=len(todo)
        print(f"batch {bnum}/{total_batches} embedded={embedded} skipped={skipped}")

    if dead_letter:
        DEAD_LETTER.write_text(json.dumps(dead_letter,indent=2))
        
    print(f"\n embedded:{embedded}")
    print(f"skipped:{skipped} (unchanged)")
    print(f"failed: {len(dead_letter)}")
    print("\n STAGE 2 done - run validate.py")
if __name__=="__main__":
    main()
    



