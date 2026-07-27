"""STAGE 3 — validation gate. Checks reality, not the run's claims."""
import os,sqlite3,sys
from pathlib import Path
from dotenv import load_dotenv
load_dotenv(Path(__file__).resolve().parent.parent/".env")
load_dotenv()

from openai import OpenAI
from pinecone import Pinecone
from config import EMBED_MODEL,EXPECTED_CHUNKS,INDEX_NAME,NAMESPACE,PARENT_DB

oai=OpenAI()
pc=Pinecone(api_key=os.environ["PINECONE_API_KEY"])
index=pc.Index(INDEX_NAME)
fails=[]

def check(label,ok,detail=""):
    print(f"    [{'PASS' if ok else 'FAIL'}] {label} {detail}")
    if not ok: fails.append(label)
print("VALIDATION\n")

count=index.describe_index_stats()["namespaces"].get(NAMESPACE,{}).get("vector_count",0)
check("vector count",count==EXPECTED_CHUNKS,f"{count}/{EXPECTED_CHUNKS}")

conn=sqlite3.connect(PARENT_DB)
probe=oai.embeddings.create(model=EMBED_MODEL,input=["revenue risk factors operations"]).data[0].embedding
sample=index.query(vector=probe,top_k=20)
missing=[m["metadata"].get("parent_id") for m in sample["matches"]
         if not conn.execute("SELECT 1 FROM parents WHERE parent_id=?",
                             (m["metadata"].get("parent_id"),)).fetchone()]
check("parent_id integrity (50 sampled)",not missing,f"{len(missing)} unresolved")

req={"ticker","form","parent_id","content_hash","embedding_model","text"}
bad=[m["id"]for m in sample["matches"] if not req<=set(m["metadata"])]
check("required metadata",not bad,f"{len(bad)} incomplete")

q=oai.embeddings.create(model=EMBED_MODEL,
                        input=["What supply chain risks does the company face?"]).data[0].embedding
res=index.query(vector=q,top_k=20,include_metadata=True,namespace=NAMESPACE)
seen,parents=set(),[]
for m in res["matches"]:
    p=m["metadata"]["parent_id"]
    if p not in seen:
        seen.add(p)
        parents.append(p)

check("smoke query returns results",len(res["matches"])>0)
print(f"  [INFO] 20 children -> {len(parents)} unique parents")
print(f"  [INFO] top: {res['matches'][0]['metadata']['ticker']} "
      f"score={res['matches'][0]['score']:.3f}")

conn.close()
print()
if fails:
    print(f"FAILED: {', '.join(fails)}"); sys.exit(1)
print("ALL CHECKS PASSED — corpus ready for retrieval")
