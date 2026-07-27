"""
Runs the chunker across all extracted filings and PERSISTS the result.

Chunking was previously computed in-memory by validate_chunker.py and
discarded. Chunks are a pipeline artifact - the embedding stage should
consume them, not re-derive them.

Free to re-run: no API calls, fully deterministic.

Reads : data/processed/<TICKER>/<TICKER>_<10K|10Q>_full.md
Writes: data/chunks/<TICKER>_<10K|10Q>.json

    python save_chunks.py
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from dry_run_normalize import normalize

from chunker import chunk_filing
_CANDIDATES = [
    Path("/Users/vishnuvardhan/Desktop/RAG AGENT/data/processed"),
    Path("/Users/vishnuvardhan/Desktop/RAG AGENT/week8/data/processed"),
]

SOURCE_DIR=next((p for p in _CANDIDATES if p.exists()),None)
OUT_DIR=Path(__file__).resolve().parent/"data"/"chunks"
FILING_LIST=None

def is_empty_table(chunk:dict)->bool:
    if not chunk.get("has_table"):
        return False
    return len(re.sub(r"[|\-\s]", "", chunk["text"])) < 25

def parse_filename(path:Path)->dict|None:
    m = re.match(r"^([A-Z][A-Z0-9.\-]*)_(10K|10Q)_full$", path.stem, re.IGNORECASE)
    if not m:
        return None
    ticker=m.group(1).upper()
    form_tag=m.group(2).upper()
    return{
        "ticker":ticker,
        "form":"10-K" if form_tag=="10K" else "10-Q",
        "form_tag":form_tag,
    }

def main()->None:
    if SOURCE_DIR is None:
        raise FileNotFoundError("data/processed not found. Set SOURCE_DIR explicitly at the top.")
    files=sorted(SOURCE_DIR.rglob("*/*_full.md"))
    if not files:
        raise FileNotFoundError(f"No *_full.md files under {SOURCE_DIR}")
    #dates=load_filing_dates()
    OUT_DIR.mkdir(parents=True,exist_ok=True)
    print(f"SOURCE:{SOURCE_DIR}")
    print(f"filings:{len(files)}\n")

    grand_total=0
    tables_dropped=0
    unlabelled=[]
    seen:dict={}
    for path in files:
        info=parse_filename(path)
        if not info:
            print(f"[skip] unrecongnized name:{path.name}")
            continue

        
        key = (info["ticker"], info["form_tag"])
        if key in seen:
            raise SystemExit(
                f"FATAL: {info['ticker']} {info['form']} appears twice.\n"
                f"  first : {seen[key]}\n"
                f"  second: {path}"
            )
        meta={"ticker":info["ticker"],"form":info["form"]}

        seen[key]=path
        
        text=path.read_text(encoding="utf-8")
        text,_=normalize(text)
        chunks=chunk_filing(text,meta)
        before=len(chunks)

        kept=[]
        for c in chunks:
            if is_empty_table(c):
                continue
            if c.get("has_table"):
                tables_dropped+=1
                continue
            kept.append(c)
        chunks=kept
        grand_total+=len(chunks)
        labelled=sum(1 for c in chunks if c.get("section_item"))
        pct=100*labelled/len(chunks) if chunks else 0
        if pct<5:
            unlabelled.append(f'{info["ticker"]} {info["form"]}')
        out_path=OUT_DIR/f"{info['ticker']}_{info["form_tag"]}.json"
        out_path.write_text(json.dumps(chunks,indent=1),encoding="utf-8")
        print(f"  {info['ticker']:<6} {info['form']:<6} "
              f"{len(chunks):>4} prose  ({before - len(chunks)} dropped)  "
              f"{pct:>5.1f}% labelled")
        
    print(f"\ntotal chunks : {grand_total:,}")
    print(f"table chunks dropped : {tables_dropped:,}")
    print(f"written to   : {OUT_DIR}")
    print(f"unlabelled   : {len(unlabelled)} filings")
    for u in unlabelled:
        print(f"               {u}")




if __name__ == "__main__":
    main()