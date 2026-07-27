"""
Verifies the triplication hypothesis instead of assuming it.

Docling's column triplication should show as UNIFORM run-length: every
cell in a row appears exactly k consecutive times, same k across the row.

    [A,A,A,B,B,B]   -> uniform, k=3   -> triplication
    [A,A,A,B]       -> not uniform    -> real data, leave alone
    [A,B,C]         -> k=1            -> normal row

If k=3 dominates in the affected filings and k=1 dominates elsewhere,
the hypothesis holds and collapsing is safe. If run-lengths are messy,
it does not and we should not collapse.
"""

from __future__ import annotations

import collections
from pathlib import Path

_C = [Path("/Users/vishnuvardhan/Desktop/RAG AGENT/data/processed"),
      Path("/Users/vishnuvardhan/Desktop/RAG AGENT/week8/data/processed")]
SRC = next((p for p in _C if p.exists()), None)
if SRC is None:
    raise SystemExit("data/processed not found")

def run_lengths(cells:list[str])->list[int]:
    runs,prev,n=[],None,0
    for c in cells:
        if c==prev:
            n+=1
        else:
            if prev is not None:
                runs.append(n)
    if prev is not None:
        runs.append(n)
    return runs

def row_factor(line:str)->int|None:
    cells=[c.strip() for c in line.strip().strip("|").split("|")]
    cells=[c for c in cells if c and not set(c)<=set("- ")]

    if not cells:
        return None
    runs=run_lengths(cells)
    return runs[0] if len(set(runs))==1 else None

UNLABELLED = {"AMZN_10K", "AMZN_10Q", "JNJ_10Q", "JPM_10Q",
              "PG_10Q", "V_10Q", "WMT_10K", "XOM_10K"}

print(f"{'filing':<20} {'rows':>7} {'k=1':>7} {'k=2':>6} {'k=3':>7} "
      f"{'k>3':>5} {'mixed':>7}")
print("-" * 66)

for p in sorted(SRC.glob("*/*_full.md")):
    stem=p.stem.replace("_full","")
    counts=collections.Counter()

    for line in p.read_text().splitlines():
        if not line.strip().startswith("|"):
            continue
        k=row_factor(line)
        if k is None:
            counts["mixed"]+=1
        elif k==1:
            counts["k1"]+=1
        elif k==2:
            counts["k2"]+=1
        elif k==3:
            counts["k3"]+=1
        else:
            counts["kbig"]+=1
    
    total=sum(counts.values()) or 1
    mark = "  <-- unlabelled" if stem in UNLABELLED else ""
    print(f"{stem:<20} {total:>7,} "
          f"{100*counts['k1']/total:>6.1f}% "
          f"{100*counts['k2']/total:>5.1f}% "
          f"{100*counts['k3']/total:>6.1f}% "
          f"{100*counts['kbig']/total:>4.1f}% "
          f"{100*counts['mixed']/total:>6.1f}%{mark}")

print("\nread: if the unlabelled filings show high k=3 and the rest show")
print("high k=1, triplication is real and structural. If k=3 is high")
print("everywhere, it is not specific to the broken filings. If mixed")
print("dominates, do not collapse.")
        



