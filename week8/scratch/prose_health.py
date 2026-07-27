"""
FilingsIQ - Prose health check across all 20 companies (Week 8, Step 11)

Checks TWO failure modes at once, no section-finding required (that's
been unreliable), no manual reading required:

  1. PROSE LOSS   -> too few prose words (real content didn't extract)
  2. DUPLICATION  -> low unique-sentence ratio (same text repeated many
                     times; volume alone would be fooled by this, so we
                     measure uniqueness explicitly). We already know this
                     filer duplicates content (the table column-triplication),
                     so prose duplication is a real thing to rule out.

Apple is the baseline - the user manually confirmed Apple's prose is good,
so Apple's numbers define "healthy". Anything wildly off from Apple is
flagged for a look.

Prose = lines that look like real sentences (long, contain lowercase words,
not table rows / ToC links / headers). Rough but robust.

USAGE (from repo root):
    python ingestion/prose_health.py
"""

import json
import re
from pathlib import Path

PROCESSED_DIR=Path("data/processed")
FILING_LIST_PATH=Path("data/filing_list.json")

def is_prose(line):
    s=line.strip()
    if len(s)<40 or s.startswith("|") or "](#" in s or s.startswith("<!--"):
        return False
    return " " in s and sum(c.islower() for c in s)>15

def analyze(ticker,form_tag):
    path=PROCESSED_DIR/ticker/f"{ticker}_{form_tag}_full.md"
    if not path.exists():
        return None
    
    prose_lines=[l.strip() for l in path.read_text().splitlines() if is_prose(l)]
    if not prose_lines:
        return {"prose_lines":0,"words":0,"uniq_ratio":0.0}
    
    words=sum(len(l.split()) for l in prose_lines)
    text=" ".join(prose_lines)
    sentences=[s.strip().lower() for s in re.split(r"(?<=[.!?])\s+", text) if len(s.strip())>30]
    total_sent=len(sentences)
    uniq_sent=len(set(sentences))
    uniq_ratio=(uniq_sent/total_sent) if total_sent else 0.0

    return {"prose_lines":len(prose_lines),"words":words,"total_sent":total_sent,"uniq_sent":uniq_sent,"uniq_ratio":uniq_ratio}

def main():
    with open(FILING_LIST_PATH) as f:
        tickers=list(dict.fromkeys(fl["ticker"] for fl in json.load(f)))

    print(f"{'TICKER':<7} {'FORM':<5}{'PROSE_WORDS':<12}{'SENTENCES':<11}{'UNIQ_RATIO':11}")
    print("-"*55)

    rows=[]
    for ticker in tickers:
        for form_tag in ["10K","10Q"]:
            r=analyze(ticker,form_tag)
            if r is None:
                continue
            rows.append((ticker,form_tag,r))
            print(f"{ticker:<7} {form_tag:<5} {r['words']:<12,} "
                  f"{r.get('total_sent', 0):<11,} {r['uniq_ratio']:<11.2f}")
        print()

    
    aapl = next((r for t, f, r in rows if t == "AAPL" and f == "10K"), None)
    if aapl:
        print("-" * 55)
        print(f"BASELINE (AAPL 10-K, user-confirmed good): "
              f"{aapl['words']:,} words, uniq_ratio {aapl['uniq_ratio']:.2f}")
        print("\nFLAGGED (words < 40% of a typical 10-K, or uniq_ratio < 0.60):")
        flagged = False
        for t, f, r in rows:
            low_words = f == "10K" and r["words"] < 0.4 * aapl["words"]
            low_uniq = r["uniq_ratio"] < 0.60 and r.get("total_sent", 0) > 50
            if low_words or low_uniq:
                flagged = True
                reason = []
                if low_words: reason.append("low prose volume")
                if low_uniq: reason.append(f"high duplication (uniq {r['uniq_ratio']:.2f})")
                print(f"  {t} {f}: {', '.join(reason)}")
        if not flagged:
            print("  none - all filings have healthy prose volume and low duplication")


if __name__ == "__main__":
    main()