import re
from pathlib import Path
from section_splitter import split_into_sections

_C = [Path("/Users/vishnuvardhan/Desktop/RAG AGENT/data/processed"),
      Path("/Users/vishnuvardhan/Desktop/RAG AGENT/week8/data/processed")]
SRC = next((p for p in _C if p.exists()), None)
if SRC is None:
    raise SystemExit("data/processed not found")

ITEM_HEADER=re.compile(r"^(Item\s*\d+A?\s*\.)\s*(.*)$", re.I)

def collapse_uniform(cells):
    runs,prev,n=[],None,0
    for c in cells:
        if c==prev:
            n+=1
        else:
            if prev is not None:
                runs.append(n)
            prev=c
            n=1
    if prev is not None:
        runs.append(n)
    if not runs or len(set(runs))!=1:
        return None
    return cells[::runs[0]]

def normalize_row(line):
    cells=[c.strip() for c in line.strip().strip("|").split("|")]
    cells=[c for c in cells if c and not set(c)<=set("- ")]
    if not cells:
        return None
    coll=collapse_uniform(cells)
    if coll is None:
        return None
    joined=re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", " ".join(coll)).strip()
    m=ITEM_HEADER.match(joined)
    if not m:
        return None
    if len(coll)>4 or len(joined)>120:
        return None
    return f"{m.group(1).strip()} {m.group(2).strip()}".strip()
    
def normalize(text):
    out,n=[],0
    for line in text.splitlines():
        if line.strip().startswith("|"):
            fixed=normalize_row(line)
            if fixed:
                out.append(fixed)
                n+=1
                continue
        out.append(line)
    return "\n".join(out),n

def coverage(text):
    secs=split_into_sections(text)
    total=sum(len(s["text"]) for s in secs) or 1
    labelled=sum(len(s["text"]) for s in secs if s.get("item"))
    return 100*labelled/total

print(f"{'filing':<22} {'before':>8} {'after':>8} {'delta':>8}  rows")
print("-" * 60)
improved = regressed = 0

for p in sorted(SRC.glob("*/*_full.md")):
    raw=p.read_text()
    before=coverage(raw)
    fixed,n=normalize(raw)
    after=coverage(fixed)
    d=after-before
    flag=""
    if d>1:
        improved+=1
        flag="<-- gained"
    elif d<-1:
        regressed+=1
        flag="<-- REGRESSED"
    print(f"{p.stem:<22} {before:>7.1f}% {after:>7.1f}% {d:>+7.1f}% {n:>5}{flag}")

print(f"\nimproved: {improved}   regressed: {regressed}")
if regressed:
    print("Do NOT apply until regressions are understood.")