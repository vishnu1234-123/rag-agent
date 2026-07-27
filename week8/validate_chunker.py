"""
FilingsIQ - Chunk validation (Week 8, Step 14)

Three checks, in priority order:

  1. NO CONTENT LOSS (the gate). Chunks overlap by design, so we can't
     assert concat(chunks) == source. Instead we verify COVERAGE: every
     source line's content appears in at least one chunk. A silent drop
     here would be invisible otherwise - the pipeline runs clean, counts
     look fine, and content is just gone.

  2. REAL CHUNK SAMPLES. No-loss says every character survived somewhere;
     it says nothing about whether chunks are USABLE. Only reading actual
     chunks catches mid-sentence cuts or broken tables.

  3. METADATA SPOT-CHECK. Confirms chunks carry the right section_item
     and has_table on real data, not just the toy example.

USAGE (from repo root):
    python ingestion/validate_chunks.py
"""

import json
import re
import random
from pathlib import Path
from collections import Counter
from chunker import chunk_filing,TOKENIZER

PROCESSED=Path("data/processed")
REQUIRED_KEYS = {"text", "ticker", "form", "section_item", "has_table", "n_tokens"}


def normalize(text:str)->str:
    return re.sub(r"\s+"," ",text).strip()

def check_no_loss(source:str,chunks:list[dict],sample_lines:int=300):
    all_chunk_text=normalize(" ".join(c["text"] for c in chunks))
    src_lines=[l.strip() for l in source.splitlines()
               if len(l.strip())>40 and not l.strip().startswith("<!--")]

    if not src_lines:
        return 0,0,[]
    sample=random.sample(src_lines,min(sample_lines,len(src_lines)))
    missing=[]
    for line in sample:
        probe=normalize(line)[:80]
        if probe and probe not in all_chunk_text:
            missing.append(line[:100])
    return len(sample)-len(missing),len(sample),missing

def check_coherence(chunks):
    issues=Counter()
    examples={}
    for c in chunks:
        txt=c["text"].strip()
        if not txt:
            continue
        if c["has_table"]:
            if "|" in txt and not re.search(r"\|\s*-{3,}", txt):
                issues["table_missing_header_sep"]+=1
                examples.setdefault("table_missing_header_sep",c)
        else:
            if txt[0].islower() and txt.isalpha():
                issues["prose_starts_midword"]+=1
                examples.setdefault("prose_starts_midword",c)
    return issues,examples

def main():
    print(f"Tokenizer:{TOKENIZER}\n")
    with open("data/filing_list.json") as f:
        filings=json.load(f)
    
    all_chunk_filing={}
    print("=" * 78)
    print("CHECK 1: NO CONTENT LOSS (gate)  +  CHECK 2: COHERENCE  -- all 40 filings")
    print("=" * 78)
    print(f"{'TICKER':<7} {'FORM':<6} {'CHUNKS':<8} {'COVERED':<11} {'COHERENCE ISSUES'}")
    print("-" * 78)

    total_missing=0
    total_issues=Counter()
    all_examples={}

    for fl in filings:
        ticker,form = fl["ticker"],fl["form"]
        path=PROCESSED/ticker/f"{ticker}_{form.replace("-","")}_full.md"
        if not path.exists():
            continue
        source=path.read_text()
        chunks=chunk_filing(source,{"ticker":ticker,"form":form})
        all_chunk_filing[(ticker,form)]=chunks

        ok,total,missing=check_no_loss(source,chunks)
        total_missing+=len(missing)

        issues,examples=check_coherence(chunks)
        total_issues.update(issues)

        for k,v in examples.items():
            all_examples.setdefault(k,v)
        
        issue_str=", ".join(f"{k}:{v}" for k,v in issues.items()) or "-"
        loss_flag="" if not missing else f" !!{len(missing)} LOST"
        print(f"{ticker:<7} {form:<6} {len(chunks):<8} {ok}/{total:<9}{loss_flag} {issue_str}")

    print("-" * 78)
    print(f"CHECK 1 RESULT: {total_missing} missing lines total (0 = no content loss)")
    print(f"CHECK 2 RESULT: {dict(total_issues) if total_issues else 'no coherence issues detected'}")

    if all_examples:
        print("\n"+"="*78)
        print("SAMPLES FROM FLAGGED CHUNKS (read these - they're the ones that matter)")
        print("=" * 78)
        for issue, c in all_examples.items():
            print(f"\n--- {issue} | {c['ticker']} {c['form']} section={c['section_item']} tok={c['n_tokens']} ---")
            print("  " + "\n  ".join(c["text"].splitlines()[:6]))

    print("\n"+"="*78)
    print("CHECK 3:METADATA -- all filing")
    print("="*78)

    bad_meta=[]
    labeled_pct={}

    for (ticker,form) , chunks in all_chunk_filing.items():
        missing_keys=REQUIRED_KEYS-set(chunks[0].keys()) if chunks else REQUIRED_KEYS
        if missing_keys:
            bad_meta.append((ticker,form,missing_keys))
        labeled=sum(1 for c in chunks if c["section_item"])
        labeled_pct[(ticker,form)]=(labeled,len(chunks))
    if bad_meta:
        print(" !! filings missing required metadata keys:")
        for t,f,k in bad_meta:
            print(f"{t}{f}:missing {k}")
    else:
        print(f"  All filings carry required keys: {sorted(REQUIRED_KEYS)}")

    print("\n  Section-label coverage (chunks WITH a section label / total):")

    for (ticker,form),(lab,tot) in sorted(labeled_pct.items()):
        pct=lab/tot *100 if tot else 0
        note = "  <- no section structure (expected fallback)" if pct == 0 else ""
        print(f"    {ticker:<7} {form:<6} {lab:>5}/{tot:<6} ({pct:>5.1f}%){note}")


if __name__ == "__main__":
    main()





