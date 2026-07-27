
import re, glob, collections

from pathlib import Path

SRC = Path("/Users/vishnuvardhan/Desktop/RAG AGENT/data/processed")

def triplicated_cells(text):

    """Count markdown cells whose content is the same value 3x."""

    hits = tot = 0

    for line in text.splitlines():

        if not line.strip().startswith("|"):

            continue

        for cell in line.split("|"):

            c = cell.strip()

            if not c or set(c) <= set("- "):

                continue

            tot += 1

            n = len(c)

            if n % 3 == 0 and n >= 6:

                third = n // 3

                if c[:third] == c[third:2*third] == c[2*third:]:

                    hits += 1

    return hits, tot

rows = []

for p in sorted(SRC.glob("*/*_full.md")):

    h, t = triplicated_cells(p.read_text())

    rows.append((p.stem, h, t, 100*h/t if t else 0))

print(f"{'filing':<24} {'trip':>7} {'cells':>8} {'pct':>6}")

for name, h, t, pct in rows:

    flag = "  <-- heavy" if pct > 20 else ""

    print(f"{name:<24} {h:>7} {t:>8} {pct:>5.1f}%{flag}")

tot_h = sum(r[1] for r in rows); tot_t = sum(r[2] for r in rows)

print(f"\ncorpus: {tot_h:,} / {tot_t:,} cells triplicated ({100*tot_h/tot_t:.1f}%)")

# does dedup recover Item headers in the unlabelled filings?

print("\n=== Item headers hidden in tables (unlabelled filings) ===")

for tick in ["AMZN", "JNJ", "PG", "V", "WMT", "XOM", "JPM"]:

    for p in SRC.glob(f"{tick}/*_full.md"):

        txt = p.read_text()

        in_table = len(re.findall(r"^\|.*Item\s*\d+A?\.", txt, re.M | re.I))

        in_prose = len(re.findall(r"^\s*Item\s*\d+A?\.", txt, re.M | re.I))

        print(f"  {p.stem:<22} in-table={in_table:>3}  in-prose={in_prose:>3}")

