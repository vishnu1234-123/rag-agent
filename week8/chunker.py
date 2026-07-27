"""
FilingsIQ - Structure-aware chunker (Week 8, Step 13)

Two-stage pipeline (composed, not branching):
  Stage 1: split_into_sections()  -> label sections by SEC 'Item N.' boundary
  Stage 2: chunk each section to token size, keeping tables atomic

LIBRARY vs CUSTOM (audited deliberately, not assumed):
  - Prose splitting -> LangChain RecursiveCharacterTextSplitter.
    Standard, battle-tested, token-aware via from_tiktoken_encoder.
    No reason to hand-roll this.
  - Section boundaries -> CUSTOM. LangChain's MarkdownHeaderTextSplitter
    splits on '#' headers, but Docling emits ZERO '#' headers for these
    filings (verified: 0 headers across all 40). It would return one giant
    chunk. SEC 'Item N.' boundaries need custom detection.
  - Table atomicity -> CUSTOM. No LangChain splitter keeps a markdown
    table whole or splits it by rows with a repeated header. Cutting a
    table mid-row severs a number from its label, which we spent this
    whole phase preventing.

Sizing in TOKENS matching OpenAI text-embedding-3-small (8,191 limit).
All sizes are CONFIG - tune against RAGAS later.

USAGE:
    from chunker import chunk_filing
    chunks = chunk_filing(markdown_text, base_metadata={...})
"""

import re
from section_splitter import split_into_sections
from langchain_text_splitters import RecursiveCharacterTextSplitter


#---CONFIG---
CHUNK_SIZE_TOKENS=800
CHUNK_OVERLAP_TOKENS=100
TABLE_MAX_TOKENS=1200
EMBED_MODEL_LIMIT=8191

try:
    _prose_splitter=RecursiveCharacterTextSplitter.from_tiktoken_encoder(
        encoding_name="cl100k_base",
        chunk_size=CHUNK_SIZE_TOKENS,
        chunk_overlap=CHUNK_OVERLAP_TOKENS,
    )
    import tiktoken
    _enc=tiktoken.get_encoding("cl100k_base")

    def n_tokens(text:str)->int:
        return len(_enc.encode(text))
    TOKENIZER="tiktoken/cl100k_base"

  
except Exception:
    _prose_splitter=RecursiveCharacterTextSplitter(
        chunk_size=CHUNK_SIZE_TOKENS*4,
        chunk_overlap=CHUNK_OVERLAP_TOKENS*4,
    )

    def n_tokens(text:str)->int:
        return max(1,len(text)//4)
    
    TOKENIZER="char-estimate (tiktoken unavailable)"

def _split_into_blocks(section_text:str)->list[dict]:
    blocks,buf,buf_is_table=[],[],False

    def flush():
        if buf:
            blocks.append({"type":"table" if buf_is_table else "prose",
                           "text":"\n".join(buf)})
    for line in section_text.splitlines():
        is_table_line=line.strip().startswith("|")
        if is_table_line!=buf_is_table and buf:
            flush()
            buf=[]
        buf_is_table=is_table_line
        buf.append(line)
    flush()
    return blocks


def _split_table_by_rows(table_text: str) -> list[str]:
    lines = [l for l in table_text.splitlines() if l.strip()]
    if len(lines) <= 2:
        return [table_text]

    header = lines[:2]
    data = lines[2:]

    pieces, cur= [], []
    for row in data:
        cur.append(row)
        if n_tokens("\n".join(header+cur))>=TABLE_MAX_TOKENS:
            pieces.append("\n".join(header+cur))
            cur=[]
    if cur:
        pieces.append("\n".join(header+cur))
    return pieces

def chunk_filing(markdown_text:str,base_metadata:dict)->list[dict]:
    chunks=[]

    for sec in split_into_sections(markdown_text):
        sec_meta={"section_item":sec["item"],"section_title":sec["title"]}

        for block in _split_into_blocks(sec["text"]):
            if block["type"]=="table":
                pieces=([block["text"]] if n_tokens(block["text"])<=TABLE_MAX_TOKENS
                        else _split_table_by_rows(block["text"]))
                for p in pieces:
                    chunks.append({"text":p ,"has_table":True,**sec_meta})
            else:
                for p in _prose_splitter.split_text(block["text"]):
                    chunks.append({"text":p,"has_table":False,**sec_meta})
    out=[]
    for i,c in enumerate(chunks):
        if not c["text"].strip():
            continue
        out.append({**base_metadata,**c,"chunk_index":i,"n_tokens":n_tokens(c["text"])})
    return out

if __name__ == "__main__":
    sample = """Item 1. Business
We design, manufacture and sell smartphones and computers. Our products include phones, tablets and laptops.

Item 1A. Risk Factors
Our business is subject to numerous risks. Competition is intense. Supply chains may be disrupted.

| Metric | 2025 | 2024 |
|--------|------|------|
| Revenue | 100 | 90 |
| Net income | 20 | 18 |
"""
    chunks = chunk_filing(sample, {"ticker": "TEST", "form": "10-K"})
    print(f"Tokenizer: {TOKENIZER}")
    print(f"Produced {len(chunks)} chunks:\n")
    for c in chunks:
        print(f"  [{c['section_item']}] has_table={c['has_table']} "
              f"tok={c['n_tokens']}: {c['text'][:55]!r}")
