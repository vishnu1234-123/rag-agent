"""
Distinguishes TOC entries from real section headers by POSITION.

A table of contents clusters in the first few percent of the document.
Real section headers spread across it: Item 1 near the start, Item 7
mid-document, Item 15 near the end.

If every match sits under 5%, that filing genuinely has no body-level
Item headers and the accepted limitation stands.
"""

import re
from pathlib import Path

_CANDIDATES = [
    Path("/Users/vishnuvardhan/Desktop/RAG AGENT/data/processed"),
    Path("/Users/vishnuvardhan/Desktop/RAG AGENT/week8/data/processed"),
]
SRC = next((p for p in _CANDIDATES if p.exists()), None)
if SRC is None:
    raise SystemExit("data/processed not found - set SRC manually")

TARGETS = [
    ("AMZN", "10K"), ("AMZN", "10Q"), ("JNJ", "10Q"), ("JPM", "10Q"),
    ("PG", "10Q"), ("V", "10Q"), ("WMT", "10K"), ("XOM", "10K"),
    ("AAPL", "10K"),   # control: known good at 90% labelled
]

PAT = re.compile(r"Item\s*(\d+A?)\s*\.", re.I)

for tick,form in TARGETS:
    p=SRC/tick/f"{tick}_{form}_full.md"
    if not p.exists():
        print(f"missing {p}")
        continue

    text=p.read_text()
    L=len(text)

    hits=[]
    for m in PAT.finditer(text):
        line_start=text.rfind("\n",0,m.start())+1
        line_end=text.find("\n",m.start())
        line=text[line_start:line_end if line_end>0 else L]
        hits.append({
            "pct":100*m.start()/L,
            "item":m.group(1).upper(),
            "table":line.strip().startswith("|"),
        })
    
    early=[h for h in hits if h["pct"]<5]
    late=[h for h in hits if h["pct"]>=5]
    late_tbl=sum(1 for h in late if h["table"])

    print(f"=== {tick} {form} ===  {len(hits)} total 'Item N.' matches")
    print(f"  first 5% (TOC zone)        : {len(early)}")
    print(f"  past 5% (candidate headers): {len(late)}   "
          f"[{late_tbl} in tables, {len(late) - late_tbl} in prose]")
    if late:
        print("  positions:", ", ".join(
            f"{h['item']}@{h['pct']:.0f}%{'T' if h['table'] else 'P'}"
            for h in late[:14]))
    print()

