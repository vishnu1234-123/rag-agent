import collections
from pathlib import Path

_C = [Path("/Users/vishnuvardhan/Desktop/RAG AGENT/data/processed"),
      Path("/Users/vishnuvardhan/Desktop/RAG AGENT/week8/data/processed")]
SRC = next((p for p in _C if p.exists()), None)
if SRC is None:
    raise SystemExit("data/processed not found")


def run_lengths(cells):
    runs = []
    prev = None
    n = 0
    for c in cells:
        if c == prev:
            n += 1
        else:
            if prev is not None:
                runs.append(n)
            prev = c
            n = 1
    if prev is not None:
        runs.append(n)
    return runs


def row_factor(line):
    cells = [c.strip() for c in line.strip().strip("|").split("|")]
    cells = [c for c in cells if c and not set(c) <= set("- ")]
    if not cells:
        return None
    runs = run_lengths(cells)
    return runs[0] if len(set(runs)) == 1 else None


UNLABELLED = {"AMZN_10K", "AMZN_10Q", "JNJ_10Q", "JPM_10Q",
              "PG_10Q", "V_10Q", "WMT_10K", "XOM_10K"}

print(f"{'filing':<20} {'rows':>7} {'k=1':>7} {'k=3':>7} {'mixed':>7}")
print("-" * 52)

for p in sorted(SRC.glob("*/*_full.md")):
    stem = p.stem.replace("_full", "")
    counts = collections.Counter()
    for line in p.read_text().splitlines():
        if not line.strip().startswith("|"):
            continue
        k = row_factor(line)
        if k is None:
            continue
        counts[k] += 1
    total = sum(counts.values()) or 1
    mark = "  <-- unlabelled" if stem in UNLABELLED else ""
    print(f"{stem:<20} {total:>7,} "
          f"{100*counts[1]/total:>6.1f}% "
          f"{100*counts[3]/total:>6.1f}% "
          f"{100*(total-counts[1]-counts[3])/total:>6.1f}%{mark}")
