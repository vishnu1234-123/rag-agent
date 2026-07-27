import collections
from pathlib import Path

_C = [Path("/Users/vishnuvardhan/Desktop/RAG AGENT/data/processed"),
      Path("/Users/vishnuvardhan/Desktop/RAG AGENT/week8/data/processed")]

SRC = next((p for p in _C if p.exists()), None)

def cells_of(line):
    cells=[c.strip() for c in line.strip().strip("|").split("|")]
    return [c for c in cells if c and not set(c)<=set("- ")]

def runs_of(cells):
    runs,prev,n=[],None,0

    for  c in cells:
        if c==prev:
            n+=1
        else:
            if prev is not None:
                runs.append(n)
            prev=c
            n=1
    if prev is not None:
        runs.append(n)
    return runs
p=SRC/"AAPL"/"AAPL_10K_full.md"
print(f"file: {p}\nexists: {p.exists()}\n")

shown=0
counts=collections.Counter()

for line in p.read_text().splitlines():
    if not line.strip().startswith("|"):
        continue

    cells=cells_of(line)
    if not cells:
        counts["blank/separator"]+=1
        continue
    runs=runs_of(cells)
    uniform=len(set(runs))==1
    counts[f"k={runs[0]}" if uniform else "mixed"]+=1
    if shown<12:
        print(f"runs={str(runs):<18} uniform={uniform} {cells[:5]}")
        shown+=1

print("\n counts (blank/separator excluded from the question):")
for k,v in counts.most_common():
    print(f"{k:<16} {v}")

