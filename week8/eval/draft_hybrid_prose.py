"""
Draft the prose half of cross-company HYBRID / cross_prose questions.
 
The hybrid generator produced exact numeric answers but left the prose half
(the "reasons each company gives" / "how each describes theme X") for humans,
because that content lives in the filings, not the DB. This helper drafts that
prose half from the REAL chunks so you verify-and-correct instead of authoring
from scratch.
 
Anti-cross-attribution design: for a 2-company question, each company's prose is
drafted in a SEPARATE LLM call that sees ONLY that company's chunks. A call can't
put Walmart's reason on Amazon because it never sees Walmart's text. The drafts
are then combined, with each clearly labeled by company and carrying its source
chunk ids for verification.
 
For each question the helper:
  1. Determines the two companies + the topic (concept-change reasons for hybrid;
     the theme for cross_prose).
  2. Retrieves candidate chunks for each company by keyword-scoring their prose
     chunks against the topic (no embeddings needed — lexical is enough to
     surface the right section for a human to verify).
  3. Drafts that company's answer from its top chunks (one LLM call).
  4. Writes back drafted_prose {company: {answer, source_chunk_ids}} and leaves
     verified=false for human sign-off.
 
Runs locally against OPENAI_API_KEY.
 
Usage:
    python draft_hybrid_prose.py --in cc_hybrid.json --chunks-dir data/chunks \
        --out cc_hybrid_drafted.json
    python draft_hybrid_prose.py --dry-run     # show retrieved chunks, no API
"""

import argparse
import json
import os
import re
import sys
from collections import defaultdict
from pathlib import Path

NAMES = {
    "AAPL": "Apple", "AMZN": "Amazon", "BA": "Boeing", "BAC": "Bank of America",
    "BRK-B": "Berkshire Hathaway", "CVX": "Chevron", "GOOGL": "Alphabet",
    "JNJ": "Johnson & Johnson", "JPM": "JPMorgan Chase", "KO": "Coca-Cola",
    "META": "Meta", "MSFT": "Microsoft", "NVDA": "NVIDIA", "PG": "Procter & Gamble",
    "T": "AT&T", "TSLA": "Tesla", "UNH": "UnitedHealth", "V": "Visa",
    "WMT": "Walmart", "XOM": "ExxonMobil",
}
CONCEPT_PHRASE = {"revenue": "revenue", "net_income": "net income",
                  "total_assets": "total assets"}
 
STOPWORDS = set("the a an and or of to in for its their as is are was were be "
                "this that which what how does do did will would over from each "
                "give gives change period fiscal year".split())

def load_chunks(chunks_dir):
    idx=defaultdict(list)
    for path in Path(chunks_dir).glob("*.json"):
        for c in json.load(open(path)):
            if c.get("has_table"):
                continue
            if c.get("n_tokens",0)<100:
                continue
            if (c.get("section_title") or "").lower()=="preamble":
                continue
            idx[c["ticker"]].append(c)
    return idx

def chunk_id(c):
    return f"{c["ticker"]}_{c["form"]}_{c["chunk_index"]:05d}"

def score_chunks(chunks,keywords,top_k=4):
    kw=[k for k in keywords if k not in STOPWORDS and len(k)>2]
    scored=[]
    for c in chunks:
        text=c["text"].lower()
        s=sum(text.count(k) for k in kw)
        if s>0:
            scored.append((s,c))
    scored.sort(key=lambda x:-x[0])
    return [c for _,c in scored[:top_k]]

def topic_for(item):
    if item["subtype"]=="hybrid":
        concept=None

        for ck in CONCEPT_PHRASE:
            if CONCEPT_PHRASE[ck] in item["question"]:
                concept=ck
                break
        cp=CONCEPT_PHRASE.get(concept,"results")
        kws=cp.split()+["increase","decrease","growth","driven",
                        "due","primarily","compared","higher","lower"]
        return kws,f"the reason for its {cp} change"
    else:
        theme=item.get("theme","")
        return theme.split(),f"its {theme}"

def companies_for(item):
    if item["subtype"]=="hybrid":
        return sorted(r["ticker"] for r in item["source_rows"])
    return item.get("companies",[])

DRAFT_PROMPT = """You are drafting a reference answer for an evaluation set, \
using ONLY the excerpts below from {company}'s SEC filing. Summarize, in 2-3 \
sentences, {topic} as stated in these excerpts. Use ONLY what is present here — \
if the excerpts do not actually discuss {topic}, respond exactly with: \
NOT_FOUND
 
Excerpts from {company}'s filing:
\"\"\"
{chunks}
\"\"\""""

def draft_company(client,model,company,topic,chunks):
    joined="\n\n---\n\n".join(c["text"][:1500] for c in chunks)
    resp=client.chat.completions.create(
        model=model,
        temperature=0.3,
        messages=[{"role":"user","content":DRAFT_PROMPT.format(
            company=company,topic=topic,chunks=joined[:8000]
        )}],
    )
    return resp.choices[0].message.content.strip()

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--in", dest="inp", default="cc_hybrid.json")
    ap.add_argument("--chunks-dir", default="data/chunks")
    ap.add_argument("--out", default="cc_hybrid_drafted.json")
    ap.add_argument("--model", default="gpt-4o-mini")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
 
    items = json.load(open(args.inp))
    chunk_idx = load_chunks(args.chunks_dir)
    if not chunk_idx:
        print(f"ERROR: no chunks in {args.chunks_dir}",file=sys.stderr)
        sys.exit(1)
    print(f"[load] chunks for {len(chunk_idx)} companies: {len(items)} questions")

    todo = [it for it in items if it["subtype"] in ("hybrid", "cross_prose")]
    print(f"[plan] {len(todo)} need prose drafts "
          f"({len(items)-len(todo)} misleading skipped)\n")
 
    if not args.dry_run:
        try:
            from openai import OpenAI
        except ImportError:
            print("ERROR: pip install openai", file=sys.stderr); sys.exit(1)
        if not os.getenv("OPENAI_API_KEY"):
            print("ERROR: OPENAI_API_KEY not set", file=sys.stderr); sys.exit(1)
        client = OpenAI()

    for i,it in enumerate(items,1):
        if it["subtype"] not in ("hybrid","cross_prose"):
            continue
        kws,topic=topic_for(it)
        comps=companies_for(it)
        drafted={}
        for tk in comps:
            name=NAMES.get(tk,tk)
            picks=score_chunks(chunk_idx.get(tk,[]),kws,top_k=4)
            if args.dry_run:
                print(f"[{it['id']}] {name}: {len(picks)} candidate chunks "
                      f"-> {[chunk_id(c) for c in picks]}")
                continue
            if not picks:
                drafted[tk] = {"company": name, "answer": "NOT_FOUND",
                               "source_chunk_ids": [],
                               "note": "no matching chunks — verify manually"}
                continue
            ans=draft_company(client,args.model,name,topic,picks)
            drafted[tk]={"company":name,"answer":ans,
                         "source_chunk_ids":[chunk_id(c) for c in picks]}
            
            flag=" (NOT FOUND)" if ans.strip()=="NOT FOUND" else ""
            print(f"  [{i}/{len(items)}] {it['id']} :: {name}{flag}")
        if not args.dry_run:
            it["drafted_prose"] = drafted
        
        json.dump(items, open(args.out, "w"), indent=2)
        nf = sum(1 for it in todo
                for d in it.get("drafted_prose", {}).values()
                if d["answer"].strip() == "NOT_FOUND")
        print(f"\n[done] drafted prose -> {args.out}")
        print(f"  {len(todo)} questions drafted; {nf} company-drafts came back "
          f"NOT_FOUND (topic not in retrieved chunks — verify those manually)")
        print("\nNEXT: review each drafted_prose against its source_chunk_ids, "
          "correct as needed, set verified=true. NOT_FOUND items mean the "
          "keyword search missed — check by hand before cutting the question.")
 
 
if __name__ == "__main__":
    main()



