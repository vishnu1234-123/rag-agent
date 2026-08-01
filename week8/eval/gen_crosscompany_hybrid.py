"""
Cross-company eval generator — Part 2: HYBRID + cross-prose questions.
 
These test the HYBRID route — questions that need BOTH the numeric path (exact
comparison from facts.sqlite) AND the prose path (retrieved narrative). No other
eval category exercises HYBRID, so this is its primary coverage.
 
Two subtypes:
  hybrid       — a numeric comparison + "what reasons does each give?"
                 The numeric half is templated exactly from the DB (verifiable);
                 the prose half asks for stated reasons, which the system must
                 retrieve from each company's filing.
  cross_prose  — a purely narrative comparison across 2 companies
                 ("how does each describe its AI strategy / main risks?").
                 No numbers; tests multi-document prose retrieval + comparison.
 
Design (option B): the generator templates the numeric comparison exactly and
attaches a prose sub-question. It does NOT pre-verify that the prose reasons
exist in the chunks — that is the job of the HUMAN verification pass (only ~14
questions, cheap to check by hand). Each item is marked verified=false and
carries the numeric provenance so verify_numeric_eval.py can check the numeric
half independently.
 
Groups are drawn from within a SECTOR (comparing Apple vs ExxonMobil is
meaningless). Same sector peer-sets as the numeric cross-company generator.
 
Usage:
    python gen_crosscompany_hybrid.py --db data/facts.sqlite --out cc_hybrid.json
"""

import argparse
import json
import random
import sqlite3
from collections import defaultdict

NAMES = {
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
    "retail/ecommerce": ["AMZN", "WMT"],
}

COMPARABLE = {k: v for k, v in SECTORS.items() if len(v) >= 2}

CONCEPT_PHRASE={
    "revenue":"revenue","net_income":"net income","total_assets": "total assets",
}

PROSE_THEMES = [
    "principal risk factors", "competitive strategy", "regulatory risks",
    "sources of revenue growth", "cybersecurity and data-protection risks",
    "supply chain or operational risks", "capital allocation priorities",
    "impact of macroeconomic conditions",
]

MISLEADING_PAIRS = [
    ("JPM", "AAPL", "total_assets",
     "a bank holds massive assets as part of its business model, so total "
     "assets vastly overstate its 'size' relative to a hardware company"),
    ("BAC", "MSFT", "total_assets",
     "bank balance sheets are structurally huge (loans/securities), making "
     "total-assets comparisons with a software firm misleading"),
    ("XOM", "V", "revenue",
     "an oil major books enormous gross revenue on physical commodity sales, "
     "while a payments network's revenue is a thin take-rate — not comparable"),
    ("WMT", "GOOGL", "revenue",
     "a retailer's revenue is gross merchandise sales at thin margins, vs. an "
     "ad company's high-margin revenue — same number, very different economics"),
    ("BRK-B", "NVDA", "total_assets",
     "a diversified holding/insurance conglomerate's assets aren't comparable "
     "to a fabless chip designer's"),
]

def fmt_usd(v):
    v=float(v)
    a=abs(v)
    if v<0:
        s="-"
    else:
        s=""
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
    for r in con.execute("SELECT ticker,concept,value,fiscal_year,source_tag FROM facts"):
        facts[r["ticker"]][r["concept"]][r["fiscal_year"]]=dict(r)
    con.close()
    return facts

def prov(row):
    return {"ticker":row["ticker"],"concept":row["concept"],
            "fiscal_year":row["fiscal_year"],"value":row["value"],
            "source_tag":row["source_tag"]}

def gen_hybrid(facts,rng,n):
    out=[]
    tries=0
    seen=set()
    sectors=list(COMPARABLE.items())
    while len(out)<n and tries<n*50:
        tries+=1
        sector,members=rng.choice(sectors)
        group=tuple(sorted(rng.sample(members,2)))
        concept=rng.choice(["revenue","net_income","total_assets"])

        shared=None

        for t in group:
            ys=set(facts.get(t,{}).get(concept,{}).keys())
            shared=ys if shared is None else (shared & ys)
        if not shared or len(shared)<2:
            continue
        ys=sorted(shared)
        y1,y2=ys[0],ys[-1]
        key=(group,concept,y1,y2)
        if key in seen:
            continue
        seen.add(key)

        growth,rows={},[]
        for t in group:
            r1,r2=facts[t][concept][y1],facts[t][concept][y2]
            rows+=[r1,r2]
            growth[t]=(r2["value"]-r1["value"])/r1["value"] if r1["value"] else 0
        faster=max(growth,key=growth.get)
        names=" and ".join(NAMES[t] for t in group)
        cp=CONCEPT_PHRASE[concept]

        out.append({
            "id": f"cc_hybrid_{concept}_{'_'.join(group)}_{y1}_{y2}",
            "category": "cross_company",
            "subtype": "hybrid",
            "expected_route": "HYBRID",
            "sector": sector,
            "question": (f"Between {names}, which grew {cp} faster from fiscal "
                         f"{y1} to {y2}, and what reasons does each give for its "
                         f"{cp} change over that period?"),
            # the numeric half is exact + checkable; the prose half is open
            "expected_numeric": {
                "faster_grower": faster,
                "growth_pct": {t: round(growth[t] * 100, 1) for t in group},
            },
            "expected_answer_numeric": (
                f"{NAMES[faster]} grew faster "
                f"({growth[faster]*100:+.1f}% vs "
                + ", ".join(f'{NAMES[t]} {growth[t]*100:+.1f}%'
                            for t in group if t != faster) + ")"),
            "prose_requirement": (
                f"Must also surface, from each company's filing, the stated "
                f"reasons for its {cp} change {y1}-{y2}. Human-verify these "
                f"reasons actually appear in {NAMES[group[0]]}'s and "
                f"{NAMES[group[1]]}'s filings."),
            "source_rows": [prov(r) for r in rows],
            "verified": False,
        })
    return out

def gen_cross_prose(facts,rng,n):
    out=[]
    tries=0
    seen=set()
    sectors=list(COMPARABLE.items())

    while len(out)<n and tries<n*50:
        tries+=1
        sector,members=rng.choice(sectors)
        group=tuple(sorted(rng.sample(members,2)))
        theme=rng.choice(PROSE_THEMES)
        key=(group,theme)
        if key in seen:
            continue
        seen.add(key)
        names=" and ".join(NAMES[t] for t in group)
        out.append({
            "id": f"cc_prose_{'_'.join(group)}_{theme.split()[0].lower()}",
            "category": "cross_company",
            "subtype": "cross_prose",
            "expected_route": "HYBRID",  # multi-doc prose retrieval + compare
            "sector": sector,
            "question": (f"How do {names} each describe their {theme} in their "
                         f"filings, and how do they differ?"),
            "prose_requirement": (
                f"Retrieve and compare {theme} from BOTH {NAMES[group[0]]}'s and "
                f"{NAMES[group[1]]}'s filings. Human-verify both companies "
                f"actually discuss '{theme}'. Answer must not attribute one "
                f"company's statements to the other."),
            "companies": list(group),
            "theme": theme,
            "verified": False,
        })
    return out

def gen_misleading(facts,rng,n):
    out=[]
    pairs=list(MISLEADING_PAIRS)
    rng.shuffle(pairs)
    for a,b,concept,why in pairs[:n]:
        ya=set(facts.get(a,{}).get(concept,{}).keys())
        yb=set(facts.get(b,{}).get(concept,{}).keys())
        shared=ya & yb
        if not shared:
            continue
        year=max(shared)
        va=facts[a][concept][year]
        vb=facts[b][concept][year]
        hi,lo= (va,vb) if va["value"]>=vb["value"] else (vb,va)
        cp=CONCEPT_PHRASE[concept]
        out.append({
            "id": f"cc_misleading_{concept}_{a}_{b}_{year}",
            "category": "cross_company",
            "subtype": "misleading_comparison",
            "expected_route": "NUMERIC",  # numbers are exact; caveat is generation
            "sector": "cross-sector (deliberate)",
            "question": (f"Which is larger by {cp} in fiscal {year}: "
                         f"{NAMES[a]} or {NAMES[b]}?"),
            "expected_numeric": {
                "larger": hi["ticker"],
                "values": {a: va["value"], b: vb["value"]},
            },
            "expected_answer_numeric": (
                f"{NAMES[hi['ticker']]} is larger by {cp} "
                f"({fmt_usd(hi['value'])} vs {fmt_usd(lo['value'])})"),
            "expected_behavior": (
                f"Give the exact figures, BUT flag that this comparison is "
                f"misleading: {why}. A good answer states the numbers and the "
                f"caveat; a bad answer presents the raw comparison as if it were "
                f"a fair 'size' ranking."),
            "source_rows": [prov(va), prov(vb)],
            "verified": False,
        })
    return out

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default="data/facts.sqlite")
    ap.add_argument("--out", default="cc_hybrid.json")
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--n-hybrid", type=int, default=9)
    ap.add_argument("--n-cross-prose", type=int, default=5)
    ap.add_argument("--n-misleading", type=int, default=3)
    args = ap.parse_args()
 
    rng = random.Random(args.seed)
    facts = load_facts(args.db)
 
    items = []
    items += gen_hybrid(facts, rng, args.n_hybrid)
    items += gen_cross_prose(facts, rng, args.n_cross_prose)
    items += gen_misleading(facts, rng, args.n_misleading)
 
    json.dump(items, open(args.out, "w"), indent=2)

    by=defaultdict(int)
    for it in items:
        by[it["subtype"]]+=1
    print(f"[done] {len(items)} cross-company HYBRID questions -> {args.out}")
    for k in ("hybrid", "cross_prose", "misleading_comparison"):
        print(f"  {k:22} {by[k]}")
    print("\n  ALL marked verified=false — human review required:")
    print("  - hybrid: confirm each company's filing states reasons for the change")
    print("  - cross_prose: confirm both companies discuss the theme")
    print("\n--- samples ---")
    for it in items[:6]:
        print(f"\n[{it['subtype']}] {it['question']}")
        if it.get("expected_answer_numeric"):
            print(f"  numeric: {it['expected_answer_numeric']}")
 
 
if __name__ == "__main__":
    main()

