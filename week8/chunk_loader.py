"""
Loads chunks from data/chunks/ and normalizes them into one shape.

THIS IS THE ONE FILE YOU MAY NEED TO ADAPT. If your chunker emitted
different field names, fix FIELD_ALIASES and nothing else changes.

Run directly to inspect what it found:
    python chunk_loader.py
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass,field
from pathlib import Path

from config import CHUNKS_DIR

FIELD_ALIASES={
    "text":["text","content","chunk_text","page_content"],
    "ticker":["ticker","symbol"],
    "form":["form","form_type","filing_type"],
    "filing_date":["filing_date","date","filed_at","period"],
    "fiscal_year":["fiscal_year","fy","year"],
    "section_item":["section_item","item","section"],
    "has_table":["has_table","is_table","contains_table"],
    "n_tokens":["n_tokens","token_count","tokens"],
    "start_char":["start_char","start","start_index","char_start"],
    "end_char":["end_char","end","end_index","char_end"],
    "source_text":["source_text","section_text","parent_text","full_text"],
}

@dataclass
class Chunk:
    id:str
    text:str
    ticker:str
    form:str
    filing_date:str
    filing_id:str
    fiscal_year:int|None=None
    section_item:str|None=None
    has_table:bool=False
    n_tokens:int|None=None
    start_char:int|None=None
    end_char:int|None=None
    source_path:str=""
    raw:dict=field(default_factory=dict,repr=False)

    @property
    def content_hash(self)->str:
        return hashlib.sha256(self.text.encode("utf-8")).hexdigest()[:16]
    @property
    def group_key(self)->tuple:
        """
        How children are grouped into parents.

        Uses section_item when present. Falls back to the filing itself
        for the ~20% of filings with no detectable Item headers, so those
        filings still get parents.
        """
        return (self.filing_id,self.section_item or "__NOSECTION__")

def _pick(d:dict,normalized:str):
    """Find a value in d using the alias list for `normalized`."""

    for alias in FIELD_ALIASES[normalized]:
        if alias in d and d[alias] not in (None,""):
            return d[alias]
        
        meta=d.get("metadata") or {}
        if alias in meta and meta[alias] not in (None,""):
            return meta[alias]
    return None

def _iter_records(path:Path):
    raw=path.read_text(encoding="utf-8")
    if path.suffix==".jsonl":
        for line in raw.splitlines():
            line=line.strip()
            if line:
                yield json.loads(line)
        return 
    data=json.loads(raw)
    if isinstance(data,list):
        yield from data
    elif isinstance(data,dict):
        for key in ("chunks","data","records","items"):
            if isinstance(data.get(key),list):
                yield from data[key]
        yield data

def _derive_filing_date(rec:dict,path:Path)->str:
    """filing_date from the record, else the filename, else 'unknown'."""

    val=_pick(rec,"filing_date")

    if val:
        return str(val)[:10]
    m=re.search(r"(\d{4}-\d{2}-\d{2})",path.stem)
    if m:
        return m.group(1)
    m=re.search(r"(\d{8})",path.stem)
    if m:
        d=m.group(1)
        return f"{d[:4]}-{d[4:6]}-{d[6:]}"
    return "unknown"

def _slug(value:str)->str:
    """Pinecone IDs must avoid whitespace and separators."""

    return re.sub(r"[^A-Za-z0-9._-]", "", str(value))

def load_chunks(chunks_dir:Path=CHUNKS_DIR)->list[Chunk]:
    files=sorted(
        p for p in chunks_dir.rglob("*")
        if p.suffix in (".json",".jsonl") and p.is_file()
    )

    if not files:
        raise FileNotFoundError(f"No .json/.jsonl files under {chunks_dir}")
    
    chunks:list[Chunk]=[]
    for path in files:
        records=list(_iter_records(path))
        for idx,rec in enumerate(records):
            text=_pick(rec,"text")
            if not text:
                continue

            ticker=_slug(_pick(rec,"ticker") or path.stem.split("_")[0])
            form=_slug(_pick(rec,"form") or "UNKNOWN")
            filing_date=_derive_filing_date(rec,path)
            filing_id=f"{ticker}_{form}"

            section_item=_pick(rec,"section_item")
            fy=_pick(rec,"fiscal_year")
            n_tok=_pick(rec,"n_tokens")

            chunks.append(Chunk(
                id=f"{filing_id}_{idx:05d}",
                text=text,
                ticker=ticker,
                form=form,
                filing_date=filing_date,
                filing_id=filing_id,
                fiscal_year=int(fy) if fy is not None and str(fy).isdigit() else None,
                section_item=str(section_item) if section_item else None,
                has_table=bool(_pick(rec,"has_table") or False),
                n_tokens=int(n_tok) if n_tok is not None and str(n_tok).isdigit() else None,
                start_char=_pick(rec,"start_char"),
                end_char=_pick(rec,"end_char"),
                source_path=str(path),
                raw=rec,
            ))
    return chunks

def has_offsets(chunks:list[Chunk])->bool:
    """True only if EVERY chunk carries usable character offsets."""
    return all(
        isinstance(c.start_char,int) and isinstance(c.end_char,int) for c in chunks
    )

if __name__=="__main__":
    cs=load_chunks()
    print(f"loaded            : {len(cs)}")
    print(f"unique filings    : {len({c.filing_id for c in cs})}")
    print(f"unique tickers    : {len({c.ticker for c in cs})}")
    print(f"with section_item : {sum(1 for c in cs if c.section_item)}")
    print(f"table chunks      : {sum(1 for c in cs if c.has_table)}")
    print(f"char offsets      : {'YES (clean slicing)' if has_offsets(cs) else 'NO (overlap stripping)'}")
    print(f"duplicate ids     : {len(cs) - len({c.id for c in cs})}")
    print("\nsample:")
    for c in cs[:2]:
        print(f"  {c.id}  fy={c.fiscal_year} item={c.section_item} "
              f"tbl={c.has_table} tok={c.n_tokens}")
        print(f"    {c.text[:90]!r}...")



    



    



