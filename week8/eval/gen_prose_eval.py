"""
Prose eval-set generator for FilingsIQ.
 
Prose ground truth is semantic, so questions can't be templated from a table.
Instead we sample real prose chunks from data/chunks/*.json and ask an LLM to
write ONE question + reference answer grounded in each chunk. The chunk IS the
ground truth: the question is answerable from it, the reference answer is drawn
from it, and the source chunk_id is recorded so retrieval can be graded later
("did the system retrieve the chunk this question came from?").
 
This is NOT correct-by-construction like the numeric/decline sets. LLM-generated
questions have failure modes (too vague, answer not actually in the chunk,
trivially keyword-matchable). So the output is a DRAFT for human verification —
every item carries the source text so you can check the question is fair before
trusting it.
 
Sampling strategy (quality of eval depends on this more than anything):
  - prose only (has_table == False), non-preamble, n_tokens >= MIN_TOKENS
  - up-weight Risk Factors and MD&A (where real analyst questions live)
  - down-weight Financial-Statement notes (number-heavy, overlaps numeric set)
  - stratify across companies so no single filer dominates
 
Runs LOCALLY against your OPENAI_API_KEY (reads it from the environment / .env).
 
Usage:
    python gen_prose_eval.py --chunks-dir data/chunks --out data/eval/prose_eval.json --n 20
    python gen_prose_eval.py --n 50 --seed 7
    python gen_prose_eval.py --dry-run          # sample + show chunks, NO api calls
"""

import argparse
import json
import os
import random
import sys
from collections import defaultdict
from pathlib import Path

MIN_TOKENS=150

SECTION_WEIGHTS = [
    ("risk factors", 3.0),
    ("management's discussion", 3.0),
    ("business", 1.5),
    ("quantitative and qualitative", 1.5),  # Item 7A
    ("financial statements", 0.15),          # notes: keep some, don't dominate
]
DEFAULT_WEIGHT = 1.0
EXCLUDE_SECTIONS = ["preamble", "exhibit","form 10-k summary"]
 
COMPANY_NAMES = {
    "AAPL": "Apple", "AMZN": "Amazon", "BA": "Boeing", "BAC": "Bank of America",
    "BRK-B": "Berkshire Hathaway", "CVX": "Chevron", "GOOGL": "Alphabet",
    "JNJ": "Johnson & Johnson", "JPM": "JPMorgan Chase", "KO": "Coca-Cola",
    "META": "Meta", "MSFT": "Microsoft", "NVDA": "NVIDIA", "PG": "Procter & Gamble",
    "T": "AT&T", "TSLA": "Tesla", "UNH": "UnitedHealth", "V": "Visa",
    "WMT": "Walmart", "XOM": "ExxonMobil",
}

def section_weight(title):
    t=(title or "").lower()
    for needle in EXCLUDE_SECTIONS:
        if needle in t:
            return 0.0
    for needle,w in SECTION_WEIGHTS:
        if needle in t:
            return w
    
    return DEFAULT_WEIGHT

def chunk_id(c,idx):
    return f"{c["ticker"]}_{c["form"]}_{idx:05d}"

def load_candidates(chunks_dir,only_tickers=None):
    candidates=[]
    for path in sorted(Path(chunks_dir).glob("*.json")):
        data=json.load(open(path))
        for i,c in enumerate(data):
            if only_tickers and c.get("ticker") not in only_tickers:
                continue
            if c.get("has_table"):
                continue
            if c.get("n_tokens",0)<MIN_TOKENS:
                continue
            w=section_weight(c.get("section_title"))
            if w<=0:
                continue
            candidates.append({
                "cid":chunk_id(c,c.get("chunk_index",i)),
                "ticker":c["ticker"],
                "form":c["form"],
                "section":c.get("section_title") or "(unlabled)",
                "section_item":c.get("section_item"),
                "text":c["text"],
                "n_tokens":c.get("n_tokens",0),
                "weight":w,
            })
    return candidates
def stratified_sample(candidates,n,rng,n_companies=None):
    denom= n_companies if n_companies else len(COMPANY_NAMES)
    per_company=max(2,(n//denom)+1)
    by_co=defaultdict(list)
    for c in candidates:
        by_co[c["ticker"]].append(c)
    picked=[]
    for tk,items in by_co.items():
        weights=[it["weight"] for it in items]
        k=min(per_company,len(items))
        chosen=_weighted_sample_no_replace(items,weights,k,rng)
        picked.extend(chosen)
    rng.shuffle(picked)
    return picked[:n]


def _weighted_sample_no_replace(items,weights,k,rng):
    items=list(items)
    weights=list(weights)
    out=[]
    for _ in range(k):
        if not items:
            break
        total=sum(weights)
        r=rng.uniform(0,total)
        acc=0
        for i,w in enumerate(weights):
            acc+=w
            if r<=acc:
                out.append(items.pop(i))
                weights.pop(i)
                break
    return out

GEN_PROMPT = """You are creating an evaluation question for a retrieval system \
over SEC filings. Below is ONE chunk of text from {company}'s {form}, from the \
section "{section}".
 
Write ONE question that:
- can be answered SOLELY from this chunk (do not require outside knowledge),
- is specific and substantive (not "what is this about"),
- is NOT answerable by simple keyword matching — require understanding,
- a financial analyst might realistically ask.
 
Then write a concise reference answer, grounded ONLY in the chunk.
 
Return STRICT JSON, no markdown, no preamble:
{{"question": "...", "reference_answer": "...", "answerable": true}}
 
If the chunk is boilerplate / has no substantive content worth a question, \
return {{"answerable": false}} and nothing else.
 
CHUNK:
\"\"\"
{text}
\"\"\""""

def call_llm(client,model,company,form,section,text):
    resp=client.chat.completions.create(
        model=model,
        temperature=0.4,
        messages=[{
            "role":"user",
            "content":GEN_PROMPT.format(
                company=company,form=form,section=section,text=text[:6000]
            ),
        }],
    )

    raw=resp.choices[0].message.content.strip()
    if raw.startswith("```"):
        raw=raw.split("```")[1].lstrip("json").strip()
    return json.loads(raw)

def is_numeric_lookup(question,answer):
    import re
    a=(answer or "").strip()
    figures = re.findall(
        r'\$[\d,]+(?:\.\d+)?'                       # $5,820  $22.39
        r'|\d+(?:\.\d+)?\s*(?:%|percent|billion|million|trillion)'  # 80%  $22.39 billion
        r'|\b\d{1,3}(?:,\d{3})+\b'                  # 273,961  (comma-grouped)
        r'|\b\d{4,}\b',                            # 273961   (4+ bare digits)
        a, re.I,
    )
    
    figures = [f for f in figures
               if not (re.fullmatch(r'(19|20)\d{2}', f))]
    words = re.findall(r'[A-Za-z]{3,}', a)

    if len(words)<=25 and len(figures)>=1:
        return True
    if len(figures)>=2 and len(words)<40:
        return True
    q=(question or "").lower()
    metric_lead = any(q.startswith(p) or f"what was the {m}" in q or f"what was {m}" in q
                      for p in ("what was the total", "what was the amount")
                      for m in ("total revenue", "revenue", "net income", "amount", "balance"))
    if metric_lead and figures:
        return True
    return False
    
def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--chunks-dir",default="data/chunks")
    ap.add_argument("--out",default="data/eval/prose_eval.json")
    ap.add_argument("--n",type=int,default=20)
    ap.add_argument("--seed",type=int,default=42)
    ap.add_argument("--model",default="gpt-4o-mini")
    ap.add_argument("--only",default=None,
                    help="comma-seperated tickers to restrict to, e.g. BAC,BRK-B")
    ap.add_argument("--dry-run",action="store_true",
                    help="sample and print chunks, make NO api calls")
    args=ap.parse_args()

    rng=random.Random(args.seed)
    only=set(t.strip() for t in args.only.split(",")) if args.only else None
    candidates=load_candidates(args.chunks_dir,only_tickers=only)
    print(f"[load] {len(candidates)} substantive prose chunks across "
          f"{len(set(c['ticker'] for c in candidates))} companies"
          + (f" (restricted to {sorted(only)})" if only else ""))
    
    sample=stratified_sample(candidates,args.n,rng)
    print(f"[sample] selected {len(sample)} chunks")
    by_sec=defaultdict(int)
    for c in sample:
        by_sec[c["section"][:30]]+=1
    for s,k in sorted(by_sec.items(),key=lambda x:-x[1]):
        print(f"    {k:3} {s}")
    
    if args.dry_run:
        print("\n[dry-run] showing 3 sampled chunks, no API calls:\n")
        for c in sample[:3]:
            print(f"--- {c['cid']} | {c['section']} | {c['n_tokens']} tok---")
            print(c["text"][:300],"...\n")
        return
    
    try:
        from openai import OpenAI
    except ImportError:
        print("ERROR: pip install openai",file=sys.stderr)
        sys.exit(1)
    if not os.getenv("OPENAI_API_KEY"):
        print("ERROR: OPENAI_API_KEY not set (check your .env)",file=sys.stderr)
        sys.exit(1)
    client=OpenAI()

    items,skipped,errors,numeric_cut=[],0,0,0

    for i,c in enumerate(sample,1):
        company=COMPANY_NAMES.get(c["ticker"],c["ticker"])
        try:
            result=call_llm(client,args.model,company,c["form"],
                            c["section"],c["text"])
        except Exception as e:
            errors+=1
            print(f"[{i}/{len(sample)}] ERROR {c['cid']}:{e}")
            continue
        if not result.get("answerable",False):
            skipped+=1
            print(f"[{i}/{len(sample)}] skip (not answerable) {c['cid']}")
            continue
        if is_numeric_lookup(result["question"],result["reference_answer"]):
            numeric_cut+=1
            print(f"[{i}/{len(sample)}] cut (numeric-lookup,not-prose) {c['cid']}")
            continue

        route="CONCEPTUAL" if any(
            k in c["section"].lower()
            for k in ("risk","management's discussion","business")
        )else "KEYWORD"

        items.append({
            "id":f"prose_{c['cid']}",
            "category":"prose",
            "subtype":"grounded",
            "expected_route":route,
            "question":result["question"],
            "reference_answer":result["reference_answer"],
            "source_chunk_id":c["cid"],
            "company":company,
            "ticker":c["ticker"],
            "form":c["form"],
            "section":c["section"],
            "source_text":c["text"],
            "verified":False,
        })
        print(f"[{i}/{len(sample)}] ok {c['cid']} -> {route}")
    
    Path(args.out).parent.mkdir(parents=True,exist_ok=True)
    json.dump(items,open(args.out,"w"),indent=2)
    print(f"\n[done] {len(items)} prose questions -> {args.out}")
    print(f"       skipped {skipped} (not answerable), "
          f"cut {numeric_cut} (numeric-lookup), {errors} errors")
    print("\nNEXT: review each item's question against source_text, set "
          "verified=true, then drop source_text for the final set.")
 
 
if __name__ == "__main__":
    main()



