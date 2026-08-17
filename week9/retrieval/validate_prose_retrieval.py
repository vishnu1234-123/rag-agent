import sys,os,json,sqlite3
from pathlib import Path
import regex as re
from filingsiq.config import PARENT_DB

HERE=Path(__file__).resolve()
from filingsiq.retrieve.prose import retrieve
ROOT=HERE.parent.parent.parent
EVAL=ROOT/"week8"/"eval"/"prose_eval.json"

_STOP = set("the a an and or of to in for on with as is are was were be been being "
            "their its it they this that these those which who what how according "
            "to from by at into over under can could may might will would their them "
            "his her our your my we you i he she has have had do does did not no "
            "primarily ultimately various".split())

def content_words(text):
    words=re.findall(r"[a-z0-9]+",(text or "").lower())
    return {w for w in words if w not in _STOP and len(w)>2}

def coverage(reference,parent_text):
    ref=content_words(reference)
    if not ref:
        return 0.0
    par=content_words(parent_text)
    return len(ref & par)/len(ref)

def main():
    top_k = int(sys.argv[1]) if len(sys.argv) > 1 else 20
    thresh = float(sys.argv[2]) if len(sys.argv) > 2 else 0.6
    data = json.load(open(EVAL))
    hits = 0
    rows = []
    for it in data:
        q = it["question"]
        tk = it.get("ticker")
        ref = it.get("reference_answer", "")
        try:
            out = retrieve(q, tickers=tk, top_k=top_k)
        except Exception as e:
            rows.append((it["id"], -1.0, f"ERROR {e}"))
            continue
        best = 0.0
        for p in out["parents"]:
            c = coverage(ref, p["text"])
            if c > best:
                best = c
        if best >= thresh:
            hits += 1
        rows.append((it["id"], best, ""))
    n = len(data)
    print(f"=== prose retrieval recall@{top_k} (content-overlap >= {thresh}) ===")
    print(f"HIT {hits}/{n}  ({100*hits/n:.1f}%)")
    # show the weakest 10 to see where retrieval misses
    rows.sort(key=lambda r: r[1])
    print("\nweakest coverage:")
    for rid, cov, err in rows[:10]:
        print(f"  {cov:5.2f}  {rid}  {err}")
    # distribution
    import statistics
    covs = [r[1] for r in rows if r[1] >= 0]
    if covs:
        print(f"\ncoverage: mean={statistics.mean(covs):.2f} "
              f"median={statistics.median(covs):.2f} "
              f"min={min(covs):.2f} max={max(covs):.2f}")
 
 
if __name__ == "__main__":
    main()