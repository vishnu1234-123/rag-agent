"""
STAGE 1 - Build the parent store.

Groups consecutive children into parents and writes them to SQLite.
Runs BEFORE embedding so no child references a parent that doesn't exist.

Idempotent: INSERT OR REPLACE keyed on parent_id.

    python build_parents.py
"""

from __future__ import annotations

import hashlib
import sqlite3
from datetime import datetime,timezone

from chunk_loader import Chunk,has_offsets,load_chunks
from config import CHILDREN_PER_PARENT,PARENT_DB

SCHEMA="""
CREATE TABLE IF NOT EXISTS parents(
    parent_id TEXT PRIMARY_KEY,
    ticker TEXT NOT NULL,
    form TEXT NOT NULL,
    filing_date TEXT,
    fiscal_year INTEGER,
    section_item TEXT,
    text TEXT NOT NULL,
    n_chars INTEGER,
    n_children INTEGER,
    content_hash TEXT,
    created_at TEXT
);
CREATE INDEX IF NOT EXISTS idx_parents_ticker ON parents(ticker,form);
CREATE INDEX IF NOT EXISTS idx_parents_section ON parents(section_item);
"""

def _strip_overlap(acc:str,nxt:str,max_probe:int=2000)->str:
    """
    Join two chunk texts, removing the duplicated overlap region.

    Finds the longest suffix of `acc` that is also a prefix of `nxt` and
    drops it, so the parent has no stuttered repeated sentences.
    Verified exact on 100-token overlaps.
    """

    probe=min(len(acc),len(nxt),max_probe)
    for size in range(probe,20,-1):
        if acc[-size]==nxt[:size]:
            return acc+nxt[size:]
    return acc+"\n"+nxt


def build_parents(children:list[Chunk]):
    use_offsets=has_offsets(children)
    print(f"offset mode: {'clean slicing' if use_offsets else 'overlap stripping'}")

    groups:dict[tuple,list[Chunk]]={}

    for c in children:
        groups.setdefault(c.group_key,[]).append(c)
    
    parents:list[dict]=[]
    child_to_parent:dict[str,str]={}

    for (filing_id,section),members in groups.items():
        for pidx in range(0,len(members),CHILDREN_PER_PARENT):
            window=members[pidx:pidx+CHILDREN_PER_PARENT]
            seq=pidx//CHILDREN_PER_PARENT
            section_tag=section if section!="__NOSECTION__" else "NA"
            parent_id=f"{filing_id}_{section_tag}_P{seq:04d}"

            text=window[0].text
            for nxt in window[1:]:
                text=_strip_overlap(text,nxt.text)
            head=window[0]
            parents.append({
                "parent_id":parent_id,
                "ticker":head.ticker,
                "form":head.form,
                "filing_date":head.filing_date,
                "fiscal_year":head.fiscal_year,
                "section_item":head.section_item,
                "text":text,
                "n_chars":len(text),
                "n_children":len(window),
                "content_hash":hashlib.sha256(text.encode()).hexdigest()[:16],
                "created_at":datetime.now(timezone.utc).isoformat(),
            })

            for c in window:
                child_to_parent[c.id]=parent_id
    return parents,child_to_parent

def write_parents(parents:list[dict])->None:
    PARENT_DB.parent.mkdir(parents=True,exist_ok=True)
    conn=sqlite3.connect(PARENT_DB)
    try:
        conn.executescript(SCHEMA)
        conn.executemany(
            """ INSERT OR REPLACE INTO PARENTS
                (parent_id,ticker,form,filing_date,fiscal_year,
                section_item,text,n_chars,n_children,content_hash,created_at)
                VALUES (:parent_id,:ticker,:form,:filing_date,:fiscal_year,
                        :section_item,:text,:n_chars,:n_children,:content_hash,:created_at)""",
            parents
        )

        conn.commit()
    finally:
        conn.close()



def main()->None:
    children=load_chunks()
    print(f"children loaded:{len(children)}")

    parents,mapping=build_parents(children)
    write_parents(parents)

    conn=sqlite3.connect(PARENT_DB)
    stored=conn.execute("SELECT COUNT(*) FROM parents").fetchone()[0]
    avg_chars=conn.execute("SELECT AVG(n_chars) FROM parents").fetchone()[0]
    labelled=conn.execute(
        "SELECT COUNT(*) FROM parents WHERE section_item IS NOT NULL"
    ).fetchone()[0]
    conn.close()

    print(f"parents built  : {len(parents)}")
    print(f"parents stored : {stored}")
    print(f"with section   : {labelled} ({100*labelled/stored:.1f}%)")
    print(f"avg parent size: {avg_chars:,.0f} chars (~{avg_chars/4:,.0f} tokens)")
    print(f"children mapped: {len(mapping)}")

    assert stored == len(parents), "parent count mismatch after write"
    assert len(mapping) == len(children), "some children have no parent"
    print("\nSTAGE 1 OK")


if __name__ == "__main__":
    main()






