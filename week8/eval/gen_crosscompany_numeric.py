"""
Cross-company eval generator — Part 1: numeric comparisons (scriptable).
 
Generates the correct-by-construction slice of the cross-company category:
comparisons and rankings across 2-3 companies, built directly from
facts.sqlite so every answer is exact. Groups are drawn from within a SECTOR,
because comparing (say) Apple vs ExxonMobil revenue is arithmetically valid but
analytically meaningless — real comparative questions are within a peer set.
 
These are route=NUMERIC (multiple SQL lookups + a comparison), NOT hybrid — no
prose is needed to answer them. The hybrid + cross-prose questions (which DO
need retrieval) are generated separately in Part 2.
 
Sub-types:
  compare_rank   — "Which of {A,B,C} had the highest {concept} in {year}?"
  compare_growth — "Which of {A,B} grew {concept} faster from {y1} to {y2}?"
  compare_gap    — "How much larger was {A}'s {concept} than {B}'s in {year}?"
 
Usage:
    python gen_crosscompany_numeric.py --db data/facts.sqlite --out cc_numeric.json
"""

import argparse
import json
import random
import sqlite3
from collections import defaultdict

COMPANY_NAMES = {
    "AAPL": "Apple", "AMZN": "Amazon", "BA": "Boeing", "BAC": "Bank of America",
    "BRK-B": "Berkshire Hathaway", "CVX": "Chevron", "GOOGL": "Alphabet",
    "JNJ": "Johnson & Johnson", "JPM": "JPMorgan Chase", "KO": "Coca-Cola",
    "META": "Meta", "MSFT": "Microsoft", "NVDA": "NVIDIA", "PG": "Procter & Gamble",
    "T": "AT&T", "TSLA": "Tesla", "UNH": "UnitedHealth", "V": "Visa",
    "WMT": "Walmart", "XOM": "ExxonMobil",
}

SECTORS = {
    "big tech": ["AAPL", "MSFT", "GOOGL", "META", "NVDA"],
    "banks": ["JPM", "BAC"],
    "energy": ["CVX", "XOM"],
    "healthcare": ["JNJ", "UNH"],
    "consumer staples": ["KO", "PG", "WMT"],
    "payments": ["V"],           # single-member, skipped for comparisons
    "retail/ecommerce": ["AMZN", "WMT"],
}

COMPARABLE_SECTORS = {k: v for k, v in SECTORS.items() if len(v) >= 2}

CONCEPT_PHRASE = {
    "revenue": "revenue", "net_income": "net income", "total_assets": "total assets",
}

def fmt_usd(v):
    v=float(v)
    a=abs(v)
    s="-" if v<0 else ""
    if a>=1e12:
        return f"{s}${a/1e12:.2f}T"
    if a>=1e9:
        return f"{s}${a/1e9:.2f}B"
    if a>=1e6:
        return f"{s}${a/1e6:.2f}M"
    return f"{s}${a:,.0f}"

def load_facts(db):
    con=sqlite3.connect(db)
    con.row_factory=sqlite3.Row
    facts=defaultdict(lambda: defaultdict(dict))
    for r in con.execute("SELECT ticker,concept,value,fiscal_year,period_end,source_tag FROM facts"):
        facts[r["ticker"]][r["concept"]][r["fiscal_year"]]=dict(r)
    
    con.close()
    return facts

def prov(row):
    return {"ticker":row["ticker"],"concept":row["concept"],
            "fiscal_year":row["fiscal_year"],
            "value":row["value"],"source_tag":row["source_tag"]}

def common_year(facts,tickers,concept,rng):
    yearsset=[]
    for t in tickers:
        ys=set(facts.get(t,{}).get(concept,{}).keys())
        if not ys:
            return None
        yearsset.append(ys)
    common = set.intersection(*yearsset)
    return rng.choice(sorted(common) if common else None)

def gen_rank(facts,rng,n):
    out=[]
    tries=0
    seen=set()
    sectors=list(COMPARABLE_SECTORS.items())
    while len(out)<n and tries<n*40:
        tries+=1
        sector,members=rng.choice(sectors)
        size=min(3,len(members)) if len(members)>=3 else 2
        group=tuple(sorted(rng.sample(members,size)))
        concept=rng.choice(["revenue","net_income","total_assets"])
        year=common_year(facts,group,concept,rng)
        if not year:
            continue
        key=(group,concept,year)
        if key in seen:
            continue
        seen.add(key)
        rows=[facts[t][concept][year] for t in group]
        winner=max(rows,key=lambda r:r["value"])
        names=", ".join(COMPANY_NAMES[t] for t in group)

        out.append({
            "id":f"cc_rank_{concept}_{'_'.join(group)}_{year}",
            "category":"cross_company",
            "subtype":"compare_rank",
            "expected_route":"NUMERIC",
            "sector":sector,
            "question":f"Among {names}, which had the highest "
                        f"{CONCEPT_PHRASE[concept]} in fiscal year {year}",
            "expected_answer": f"{COMPANY_NAMES[winner['ticker']]}"
                                f"({fmt_usd(winner["value"])})",
            "expected_value":winner["ticker"],
            "source_rows":[prov(r) for r in rows]
        })
    return out

def gen_growth(facts,rng,n):
    out=[]
    tries=0
    seen=set()
    sectors=list(COMPARABLE_SECTORS.items())
    while len(out)<n and tries<n*40:
        tries+=1
        sector,members=rng.choice(sectors)
        group=tuple(sorted(rng.sample(members,2)))
        concept=rng.choice(["revenue","net_income","total_assets"])
        shared=None

        for t in group:
            ys=set(facts.get(t,{}).get(concept,{}).keys())
            shared= ys if shared is None else (shared & ys)
        if not shared or len(shared)<2:
            continue
        ys=sorted(shared)
        y1,y2=ys[0],ys[-1]
        key=(group,concept,y1,y2)
        if key in seen:
            continue
        seen.add(key)
        growth={}
        rows=[]

        for t in group:
            r1,r2=facts[t][concept][y1],facts[t][concept][y2]
            rows+=[r1,r2]
            growth[t]=(r2["value"]-r1["value"])/r1["value"] if r1["value"] else 0

        winner=max(growth,key=growth.get)
        names=" and ".join(COMPANY_NAMES[t] for t in group)
        out.append({
            "id":f"cc_growth_{concept}_{'_'.join(group)}_{y1}_{y2}",
            "category":"cross_company",
            "subtype":"compare_growth",
            "expected_route":"NUMERIC",
            "sector":sector,
            "question":f"Between {names}, which grew {CONCEPT_PHRASE[concept]}"
                        f"faster from fiscal {y1} to {y2}?",
            "expected_answer": f"{COMPANY_NAMES[winner]} "
                               f"({growth[winner]*100:+.1f}% vs "
                               + ", ".join(f'{COMPANY_NAMES[t]} {growth[t]*100:+.1f}%'
                                           for t in group if t != winner) + ")",
            "expected_value": winner,
            "source_rows": [prov(r) for r in rows],
        })
    return out

def gen_gap(facts,rng,n):
    out=[]
    tries=0
    seen=set()
    sectors=list(COMPARABLE_SECTORS.items())
    while len(out)<n and tries<n*40:
        tries+=1
        sector,members=rng.choice(sectors)
        group=tuple(sorted(rng.sample(members,2)))
        concept=rng.choice(["revenie","net_income","total_assets"])
        year=common_year(facts,group,concept,rng)
        if not year:
            continue
        key=(group,concept,year)
        if key in seen:
            continue
        seen.add(key)
        a,b=group
        ra,rb=facts[a][concept][year],facts[b][concept][year]
        hi,lo=(ra,rb) if ra["value"]>=rb["value"] else (rb,ra)
        gap=hi["value"]-lo["value"]
        out.append({
            "id":f"cc_gap_{concept}_{a}_{b}_{year}",
            "category":"cross_company",
            "subtype":"compare_gap",
            "expected_route":"NUMERIC",
            "sector":sector,
            "question": f"In fiscal year {year}, how much larger was "
                        f"{COMPANY_NAMES[hi['ticker']]}'s {CONCEPT_PHRASE[concept]} "
                        f"than {COMPANY_NAMES[lo['ticker']]}'s?",
            "expected_answer": f"{fmt_usd(gap)} larger "
                               f"({fmt_usd(hi['value'])} vs {fmt_usd(lo['value'])})",
            "expected_value": gap,
            "source_rows": [prov(hi), prov(lo)],
        })
    return out

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default="data/facts.sqlite")
    ap.add_argument("--out", default="cc_numeric.json")
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--n-rank", type=int, default=3)
    ap.add_argument("--n-growth", type=int, default=2)
    ap.add_argument("--n-gap", type=int, default=1)
    args = ap.parse_args()
 
    rng = random.Random(args.seed)
    facts = load_facts(args.db)
 
    items = []
    items += gen_rank(facts, rng, args.n_rank)
    items += gen_growth(facts, rng, args.n_growth)
    items += gen_gap(facts, rng, args.n_gap)
 
    json.dump(items, open(args.out, "w"), indent=2)

    by=defaultdict(int)
    for it in items:
        by[it["subtype"]]+=1
    print(f"[done] {len(items)} cross-company numeric questions -> {args.out}")
    for k in ("compare_rank","compare_growth","compare_gap"):
        print(f" {k:15}{by[k]}")
    print("\n--- samples ---")
    for it in items:
        print(f"\nQ: {it['question']}")
        print(f"A: {it['expected_answer']}")

if __name__=="__main__":
    main()

