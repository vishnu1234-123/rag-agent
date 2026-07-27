import re
from pathlib import Path

SRC = Path("/Users/vishnuvardhan/Desktop/RAG AGENT/data/processed")  # adjust if needed

for tick, form in [("AMZN","10K"), ("WMT","10K"), ("XOM","10K"), ("PG","10Q")]:
    p = SRC / tick / f"{tick}_{form}_full.md"
    if not p.exists():
        print(f"missing {p}"); continue
    print(f"=== {tick} {form} ===")
    n = 0
    for line in p.read_text().splitlines():
        if line.strip().startswith("|") and re.search(r"Item\s*\d+A?\.", line, re.I):
            print(f"  {line[:150]}")
            n += 1
            if n >= 4: break
    print()
