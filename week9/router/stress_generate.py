"""
Adversarial stress-test GENERATOR for the query router.
 
Purpose: probe the FROZEN router for systematic weaknesses — not to tune against.
The router must NOT be changed to pass this set; it is a held-out diagnostic.
 
How labels stay honest: we ask the LLM to generate questions whose correct route
is fixed BY CONSTRUCTION (e.g. "write a question that should route NUMERIC, phrased
in an unusual/terse way"). The label comes from the generation instruction, not from
the LLM judging an existing question. You then spot-check a sample before trusting it.
 
Each "attack style" targets a specific soft spot we know about:
  - terse:        "Apple revenue 2024" (no sentence frame)
  - implicit_co:  company only in context, question says "the company"
  - boundary:     prose-about-a-number ("what drove the revenue increase")
  - typo:         near-miss company spelling
  - verbose:      buried intent under clauses
  - reject_subtle: out-of-scope but phrased to look answerable
 
Usage:
  python stress_generate.py --out stress_set.json --per-style 8
  # then spot-check stress_set.json by hand, then:
  python stress_run.py --in stress_set.json
"""

import argparse
import json
import os
import re
import sys

IN_CORPUS = ["Apple", "Amazon", "Boeing", "Bank of America", "Berkshire Hathaway",
             "Chevron", "Alphabet", "Johnson & Johnson", "JPMorgan Chase",
             "Coca-Cola", "Meta", "Microsoft", "NVIDIA", "Procter & Gamble",
             "AT&T", "Tesla", "UnitedHealth", "Visa", "Walmart", "ExxonMobil"]
OUT_CORPUS = ["PepsiCo", "Netflix", "Oracle", "Disney", "Ford", "Intel",
              "Starbucks", "Nike", "Pfizer", "Shell", "Target"]
CONCEPTS = ["revenue", "net income", "total assets"]
OUT_CORPUS_NOVEL = ["Rivian", "Spotify", "Snowflake", "Palantir", "Roku",
                    "DoorDash", "Coinbase", "Airbnb", "Uber", "Lyft"]
STYLES = [
    ("terse", "NUMERIC",
     "Terse fragments with no sentence frame, e.g. 'Apple revenue 2024' or "
     "'Walmart net income FY2023'. Use an in-corpus company, a supported concept "
     "(revenue/net income/total assets), and a year in 2021-2025."),
    ("implicit_co", "CONCEPTUAL",
     "Prose questions about a filing's narrative (risks, strategy, factors, "
     "reasons) that refer to the company only as 'the company' or 'it' — do NOT "
     "name the company. These should still be answerable prose questions."),
    ("boundary", "CONCEPTUAL",
     "Questions asking for the NARRATIVE REASONS behind a numeric change — e.g. "
     "'what drove the increase in revenue', 'why did net income fall'. They "
     "mention a numeric concept but ask for explanation, not a number. Use "
     "in-corpus companies."),
    ("verbose", "NUMERIC",
     "A single numeric lookup (a supported concept + in-corpus company + a year "
     "2021-2025) buried under two or three subordinate clauses so the core ask "
     "is hard to spot. The correct answer is still a single number."),
    ("typo", "REJECT",
     "Numeric lookups where the company name is MISSPELLED as a near-miss of an "
     "in-corpus company (e.g. 'Chevorn', 'Micrsoft', 'JP Morgan Chse'). These "
     "should be rejected (or flagged as a typo), not answered."),
    ("reject_subtle", "REJECT",
     "Questions that look answerable but are out of scope: an out-of-corpus "
     "company (PepsiCo, Netflix, etc.) asked naturally, OR a supported concept "
     "for an impossible year (e.g. 2035, 1990), OR an UNsupported numeric "
     "concept (gross margin, free cash flow, EPS) asked as a number."),
    ("reject_novel_co", "REJECT",
     "Numeric or prose questions about companies that are NOT in the corpus and "
     "are newer/less-obvious names, using these specifically: "
     + ", ".join(OUT_CORPUS_NOVEL) + ". These must be rejected — the corpus has "
     "no data on them."),
    ("hybrid_hard", "HYBRID",
     "Cross-company questions that need BOTH a numeric comparison AND the "
     "narrative reasons — e.g. 'which of X and Y grew revenue more, and why does "
     "each say it happened'. Use two in-corpus companies and a supported concept."),
]
 
GEN_SYSTEM = """You generate ADVERSARIAL test questions for a financial-filings \
query router covering 20 US companies (filings 2021-2025) with three numeric \
concepts: revenue, net income, total assets. You are trying to make the router \
FAIL by phrasing questions in hard ways. Return ONLY a JSON array of strings \
(the questions), no other text, no markdown fences. Make them varied and genuinely \
tricky, not templated."""

def generate_style(client,model,style_name,expected,instruction,n):

    user=(f"Generate {n} adversarial questions in this style:\n{instruction}\n\n"
            f"In-corpus companies: {', '.join(IN_CORPUS)}\n"
            f"Out-of-corpus (for reject cases): {', '.join(OUT_CORPUS)}\n"
            f"Return ONLY a JSON array of {n} question strings.")

    resp=client.chat.completions.create(
        model=model,temperature=1.0,
        messages=[{"role":"system","content":GEN_SYSTEM},
                    {"role":"user","content":user}],
    )
    raw=resp.choices[0].message.content.strip()
    raw = re.sub(r"^```(?:json)?|```$", "", raw, flags=re.MULTILINE).strip()
    questions=json.loads(raw)
    return [{"question":q,"expected_route":expected,"style":style_name}
            for q in questions if isinstance(q,str) and q.strip()]

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--out",default="stress_set.json")
    ap.add_argument("--per-style",type=int,default=8)
    ap.add_argument("--model",default="gpt-4o-mini")
    args=ap.parse_args()

    try:
        from openai import OpenAI
    except ImportError:
        print("ERROR: pip install openai",file=sys.stderr)
        sys.exit(1)
    if not os.getenv("OPENAI_API_KEY"):
        print("ERROR: OPENAI_API_KEY not set",file=sys.stderr)
        sys.exit(1)
    client=OpenAI()

    all_items=[]
    for name,expected,instruction in STYLES:
        print(f"[gen] {name} ({expected}) ...",end=" ",flush=True)
        try:
            items=generate_style(client,args.model,name,expected,instruction,args.per_style)
            all_items.extend(items)
            print(f"{len(items)} questions")
        except Exception as e:
            print(f"FAILED: {e}")
    
    json.dump(all_items,open(args.out,"w"),indent=2)
    print(f"\n[done] {len(all_items)} questions -> {args.out}")
    print("NEXT: spot-check the file by hand (are the expected_route labels fair?), "
          "then run stress_run.py")
 
 
if __name__ == "__main__":
    main()
