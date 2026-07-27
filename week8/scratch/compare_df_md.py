import re
from pathlib import Path

_C = [Path("/Users/vishnuvardhan/Desktop/RAG AGENT/data/processed"),
      Path("/Users/vishnuvardhan/Desktop/RAG AGENT/week8/data/processed")]
SRC = next((p for p in _C if p.exists()), None)

p = SRC / "XOM" / "XOM_10K_tables.txt"
if not p.exists():
    print(f"no tables.txt at {p}")
    raise SystemExit

text = p.read_text()
print(f"tables.txt total size: {len(text):,} chars")
print("(the markdown had a single 107,363-char table chunk)\n")

# every table header line looks like: --- Table 3 shape=(15, 4) ---
shapes = re.findall(r'--- Table (\d+) shape=\(([^)]+)\) ---', text)
print(f"tables found: {len(shapes)}\n")

# flag any table that is absurdly wide (the signature-page signature)
print("widest tables by column count:")
parsed = []
for num, shape in shapes:
    rows, cols = [int(x.strip()) for x in shape.split(',')]
    parsed.append((cols, rows, num))
parsed.sort(reverse=True)
for cols, rows, num in parsed[:8]:
    flag = "  <-- absurdly wide" if cols > 20 else ""
    print(f"  Table {num}: {rows} rows x {cols} cols{flag}")

print(f"\nmedian cols: {sorted(c for c,_,_ in parsed)[len(parsed)//2]}")
