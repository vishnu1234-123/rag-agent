import re,statistics
from pathlib import Path

_C = [Path("/Users/vishnuvardhan/Desktop/RAG AGENT/data/processed"),
      Path("/Users/vishnuvardhan/Desktop/RAG AGENT/week8/data/processed")]

SRC=next((p for p in _C if p.exists()), None)

PAT = re.compile(r"Item\s*(\d+A?)\s*\.", re.I)

for tick,form in [("AAPL","10K"),("AMZN","10K"),("AMZN","10Q"),
                   ("PG","10Q"),("V","10Q"),("XOM","10K"),("WMT","10K")]:
    p=SRC/tick/f"{tick}_{form}_full.md"
    if not p.exists():
        continue

    text=p.read_text()
    L=len(text)
    pos=[(m.start(),m.group(1).upper()) for m in PAT.finditer(text) if 100*m.start()/L>=5]

    if not pos:
        print(f"{tick} {form}: none past 5%")
        continue
    
    gaps=[pos[i+1][0]-pos[i][0] for i in range(len(pos)-1)]
    real=sum(1 for g in gaps if g>2000)
    print(f"\n=== {tick} {form} ===  {len(pos)} candidates")
    print(f"  median gap: {statistics.median(gaps):>7,.0f} chars")
    print(f"  gaps >2000 chars (real content): {real}/{len(gaps)}")
    # what actually follows the widest-gap candidate
    widest = max(range(len(gaps)), key=lambda i: gaps[i])
    snippet = text[pos[widest][0]:pos[widest][0]+140].replace("\n"," ")
    print(f"  after Item {pos[widest][1]} (+{gaps[widest]:,} chars): {snippet!r}")