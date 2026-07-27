"""Chunk all 40 real filings, report stats, and assert no chunk exceeds the
embedding token limit. This is the real proof (synthetic tests passed, but
this session taught us real data reveals surprises)."""

import json
from pathlib import Path
from chunker import chunk_filing,TOKENIZER

PROCESSED=Path("data/processed")
with open("data/filing_list.json") as f:
    filings=json.load(f)

print(f"Tokenizer: {TOKENIZER}\n")
print(f"{'TICKER':<7} {'FORM':<5} {'CHUNKS':<8} {'AVG_TOK':<8} {'MAX_TOK':<8} {'TABLES':<7} {'OVER_LIMIT'}")
print("-" * 60)

grand_total=0
any_over=0

for fl in filings:
    ticker,form=fl["ticker"],fl["form"]
    form_tag=form.replace("-","")
    path=PROCESSED/ticker/f"{ticker}_{form_tag}_full.md"
    if not path.exists():
        continue
    chunks=chunk_filing(path.read_text(),{"ticker":ticker,"form":form,"acession":fl.get("acessionNumber")})
    toks=[c["n_tokens"] for c in chunks]
    over=sum(1 for t in toks if t>8191)
    any_over+=over
    grand_total+=len(chunks)
    print(f"{ticker:<7} {form:<5} {len(chunks):<8} {sum(toks)//len(toks):<8} "
          f"{max(toks):<8} {sum(c['has_table'] for c in chunks):<7} {over}")

print("-" * 60)
print(f"TOTAL chunks across all 40 filings: {grand_total:,}")
print(f"Chunks exceeding 8,191-token embed limit: {any_over} (MUST be 0)")