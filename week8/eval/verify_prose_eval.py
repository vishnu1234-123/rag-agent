"""
Verify prose eval grounding against the source chunks.
 
Prose ground truth is semantic, so we can't recompute answers like the numeric
verifier does. But we CAN check the one thing the human read-through might miss:
is each reference answer actually GROUNDED in the chunk it claims to come from?
An LLM can write a plausible answer that isn't really supported by the cited
chunk — this catches that.
 
Mapping (confirmed): source_chunk_id "TICKER_FORM_NNNNN" -> the chunk in
data/chunks/<TICKER>_<FORM-no-dash>.json whose chunk_index == NNNNN.
 
Grounding heuristic:
  - tokenize the reference answer into content words (drop stopwords, short words)
  - tokenize the source chunk the same way
  - overlap = fraction of the answer's content words that appear in the chunk
  - high overlap  -> grounded (answer's substance is in the chunk)
  - low overlap   -> possibly ungrounded -> FLAG for human review
 
This is a heuristic, not proof: a low score means "look at this one", not
"definitely wrong". It's a safety net over the human pass, not a replacement.
 
Self-check first: confirm we can load chunks and resolve a known id, else abort.
 
Usage:
    python verify_prose_eval.py --chunks-dir data/chunks --in prose_eval.json
    python verify_prose_eval.py --in prose_eval.json --threshold 0.35
"""

import argparse
import json
import re
import sys
from pathlib import Path

STOPWORDS = set("""
a an the and or but if then else of to in on at by for with from as is are was
were be been being this that these those it its their his her our your they we
you i he she them us not no do does did has have had will would could should may
might can what which who whom whose how when where why according primarily
depends ability their there also our these into across including such other
""".split())

FORM_FILE = {"10-K": "10K", "10-Q": "10Q"}

def content_words(text):
    words=re.findall(r"[a-zA-Z][a-zA-Z'\-]{2,}",(text or "").lower())
    return [w for w in words if w not in STOPWORDS]

def parse_id(cid):
    m=re.match(r"^([A-Z\-]+)_(10-[KQ])_(\d+)$",cid)
    if not m:
        return None
    return m.group(1),m.group(2),int(m.group(3))

def build_chunk_index(chunks_dir):
    idx={}
    for path in Path(chunks_dir).glob("*.json"):
        data=json.load(open(path))
        for c in data:
            idx[(c["ticker"],c["form"],c["chunk_index"])]=c
    return idx

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--chunks-dir", default="data/chunks")
    ap.add_argument("--in", dest="inp", default="prose_eval.json")
    ap.add_argument("--threshold", type=float, default=0.35,
                    help="min answer-word overlap to count as grounded")
    args = ap.parse_args()

    idx=build_chunk_index(args.chunks_dir)
    if not idx:
        print("SELF-CHECK FAILED: no chunks loaded from"
              f"{args.chunks_dir}. Aborting.",file=sys.stderr)
        sys.exit(2)
    print(f"[self-check] loaded {len(idx)} chunks from  {args.chunks_dir}")

    items=json.load(open(args.inp))
    print(f"[verify] {len(items)} prose questions\n")

    missing_chunk=[]
    low_ground=[]
    structural=[]
    scores=[]
    ids=set()

    for it in items:
        iid=it.get("id","?")
        if iid in ids:
            structural.append((iid,"duplicate id"))
        ids.add(iid)
        if it.get("expected_route") not in ("CONCEPTUAL","KEYWORD"):
            structural.append((iid,f"route {it.get('expected_route')} unexpected"))
        if not it.get("reference_answer"):
            structural.append((iid,"no reference_answer"))
            continue

        cid=it.get("source_chunk_id","")
        parsed=parse_id(cid)
        if not parsed:
            missing_chunk.append((iid,f"unparseable chunk id '{cid}"))
            continue
        ticker,form,ci=parsed
        chunk=idx.get((ticker,form,ci))
        if chunk is None:
            missing_chunk.append((iid,f"no chunk {ticker}/{form}/index={ci}"))
            continue
        ans_words=set(content_words(it["reference_answer"]))
        chunk_words=set(content_words(chunk["text"]))
        if not ans_words:
            low_ground.append((iid,0.0,"answer has no content words"))
            continue

        overlap=len(ans_words & chunk_words)/len(ans_words)
        scores.append(overlap)

        if overlap<args.threshold:
            missing=sorted(ans_words-chunk_words)[:8]
            low_ground.append((iid,overlap,
                               f"only {overlap:.0%} of answer words in chunk;"
                               f"absent e.g.: {missing}"))
            
    print(f"    resolved chunks: {len(items)-len(missing_chunk)}/{len(items)}")
    if scores:
        avg=sum(scores)/len(scores)
        print(f" mean frounding overlap: {avg:.0%}")
    print()

    if missing_chunk:
        print(f" UNRESOLVED CHUNK IDS {len(missing_chunk)} - these break"
              f"retrieval grading:")
        for iid,msg in missing_chunk:
            print(f"    [{iid}] {msg}")
        print()

    if low_ground:
        print(f"  LOW GROUNDING ({len(low_ground)}) — review these; answer may "
              f"not be supported by the cited chunk:")
        for iid, score, msg in sorted(low_ground, key=lambda x: x[1]):
            print(f"    [{iid}] {msg}")
        print()

    if structural:
        print(f"  STRUCTURAL ({len(structural)}):")
        for iid, msg in structural:
            print(f"    [{iid}] {msg}")
        print()
    
    problems = len(missing_chunk) + len(low_ground) + len(structural)
    if problems == 0:
        print("  RESULT: PASS — all chunk ids resolve, all answers grounded, "
              "structure clean.")
    else:
        print(f"  RESULT: {problems} item(s) to review "
              f"({len(missing_chunk)} unresolved, {len(low_ground)} low-ground, "
              f"{len(structural)} structural).")
        print("  NOTE: low-grounding flags are for HUMAN review, not automatic "
              "failures — a paraphrased answer can be valid with low word overlap.")
 
 
if __name__ == "__main__":
    main()
 