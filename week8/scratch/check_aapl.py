from pathlib import Path

_C = [Path("/Users/vishnuvardhan/Desktop/RAG AGENT/data/processed"),
      Path("/Users/vishnuvardhan/Desktop/RAG AGENT/week8/data/processed")]
SRC = next((p for p in _C if p.exists()), None)

def cells_of(line):
    cells = [c.strip() for c in line.strip().strip("|").split("|")]
    return [c for c in cells if c and not set(c) <= set("- ")]

def run_lengths(cells):
    runs, prev, n = [], None, 0
    for c in cells:
        if c == prev: n += 1
        else:
            if prev is not None: runs.append(n)
            prev, n = c, 1
    if prev is not None: runs.append(n)
    return runs

def factor(cells):
    runs = run_lengths(cells)
    return runs[0] if runs and len(set(runs)) == 1 else None

p = SRC / "AAPL" / "AAPL_10K_full.md"
shown = 0
print("=== sample of the k=3 rows in AAPL 10-K ===\n")
for line in p.read_text().splitlines():
    if not line.strip().startswith("|"): continue
    cells = cells_of(line)
    if factor(cells) == 3 and shown < 20:
        print(f"raw:      {cells[:6]}")
        print(f"collapse: {cells[::3]}\n")
        shown += 1
