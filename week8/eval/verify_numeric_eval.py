import argparse
import json
import sqlite3
import sys
from collections import defaultdict

NAMES = {
    "AAPL": "Apple", "AMZN": "Amazon", "BA": "Boeing", "BAC": "Bank of America",
    "BRK-B": "Berkshire Hathaway", "CVX": "Chevron", "GOOGL": "Alphabet",
    "JNJ": "Johnson & Johnson", "JPM": "JPMorgan Chase", "KO": "Coca-Cola",
    "META": "Meta", "MSFT": "Microsoft", "NVDA": "NVIDIA", "PG": "Procter & Gamble",
    "T": "AT&T", "TSLA": "Tesla", "UNH": "UnitedHealth", "V": "Visa",
    "WMT": "Walmart", "XOM": "ExxonMobil",
}

REL_TOL=1e-6

def load_facts(db):
    con=sqlite3.connect(db)
    facts=defaultdict(lambda: defaultdict(dict))
    for t,c,y,v in con.execute("SELECT ticker,concept,fiscal_year,value FROM facts"):
        facts[t][c][y]=v
    
    con.close()
    return facts

def self_check(facts):
    ok=True
    for concept in ("revenue","net_income","total_assets"):
        vals=facts.get("AAPL",{}).get(concept,{})
        if not vals or max(vals.values())<=0:
            print(f"SELF-CHECK FAILED: cannot read AAPL {concept}. Verifier "
                  f"can't see known-good data; aborting.", file=sys.stderr)
            ok=False
    if not ok:
        sys.exit(2)

def approx(a,b):
    if a==b:
        return True
    try:
        return abs(a-b)<=REL_TOL*max(abs(a),abs(b),1.0)
    except TypeError:
        return False
    
def check_item(it,facts):
    sub=it.get("subtype")
    sr={(r["ticker"],r["concept"],r["fiscal_year"]) : r["value"] for r in it.get("source_rows",[])}

    def val(t,c,y):
        return facts.get(t,{}).get(c,{}).get(y)
    
    if sub=="point":
        (t,c,y),_=next(iter(sr.items()))
        db=val(t,c,y)
        if db is None:
            return f"DB has no value for {t}/{c}/{y}"
        if not approx(it["expected_value"],db):
            return f"point: expected_value {it["expected_value"]}!=DB {db}"
        return None
    if sub=="yoy":
        keys=sorted(sr.keys(),key=lambda k:k[2])
        (t1,c1,y1),(t2,c2,y2)=keys[0],keys[1]
        recomputed=val(t2,c2,y2)-val(t1,c1,y1)
        if not approx(it['expected_value'],recomputed):
            return f"yoy: expected_value {it["expected_value"]} != recomputed {recomputed}"
        return None
    
    if sub=="trend":
        keys=sorted(sr.keys(),key=lambda k:k[2])
        (t1,c1,y1),(t2,c2,y2)=keys[0],keys[-1]
        recomputed=val(t2,c2,y2)-val(t1,c1,y1)
        if not approx(it["expected_value"],recomputed):
            return f"trend: expected_value {it["expected_value"]}!=recomputed {recomputed}"
        ans=it.get("expected_answer","").lower()
        if recomputed>0 and ("grew" not in ans and "increased" not in ans):
            return f"trend: value up but answer says '{ans[:30]}'"
        if recomputed<0 and ("shrank" not in ans and "decreased" not in ans):
            return f"trend: value down but answer says '{ans[:30]}'"
        return None
    if sub=="ranking":
        concept=next(iter(sr.keys()))[1]
        year=next(iter(sr.keys()))[2]
        rows={t:val(t,c,y) for (t,c,y) in sr.keys()}
        true_winner=max(rows,key=rows.get)
        if it["expected_value"]!=true_winner:
            return (f"ranking: expected winner {it['expected_value']} != "
                    f"argmax {true_winner} ({rows})")
        return None
    
    if sub=="compare_rank":
        rows={t:val(t,c,y) for (t,c,y) in sr.keys()}
        true_winner=max(rows,key=rows.get)
        if it["expected_value"]!=true_winner:
            return f"compare_rank: expected {it["expected_value"]}!=argmax {true_winner}"
        return None
    
    if sub=="compare_growth":
        byt=defaultdict(dict)
        for (t,c,y) in sr.keys():
            byt[t][y]=val(t,c,y)
        growth={}
        for t,ys in byt.items():
            y1,y2=min(ys),max(ys)
            base=ys[y1]
            growth[t]=(ys[y2]-base)/base if base else 0
        true_winner=max(growth,key=growth.get)
        if it["expected_value"]!=true_winner:
            return (f"compare_growth: expected {it['expected_value']} !="
                    f"fastest {true_winner} ({ {k: round(v,3) for k,v in growth.items()}})")
        return None
    
    if sub=="compare_gap":
        rows={t:val(t,c,y) for (t,c,y) in sr.keys()}
        hi=max(rows.values())
        lo=min(rows.values())
        recomputed_gap=hi-lo
        if not approx(it["expected_value"],recomputed_gap):
            return f"compare_gap: expected {it['expected_value']}!= recomputed {recomputed_gap}"
        return None
    return f"unknown subtype '{sub}'"

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--db",default="data/facts.sqlite")
    ap.add_argument("--in",dest="inp",nargs="+",default=["numeric_eval.json"])
    args=ap.parse_args()

    facts=load_facts(args.db)
    self_check(facts)
    print("[self-check] verifier reads known-good data OK\n")

    grand_total=0
    grand_fail=0
    for path in args.inp:
        items=json.load(open(path))
        by_sub=defaultdict(int)
        fails=[]
        ids=set()
        for it in items:
            by_sub[it.get("subtype","?")]+=1
            iid=it.get("id","")
            if iid in ids:
                fails.append((iid,"duplicate id"))
            ids.add(iid)
            if it.get("expected_route") not in ("NUMERIC",):
                fails.append((iid,f"route {it.get("expected_route")}!=NUMERIC"))
            if not it.get("source_rows"):
                fails.append((iid,"no source_rows to recompute from"))
                continue
            err=check_item(it,facts)
            if err:
                fails.append((iid,err))
        grand_total+=len(items)
        grand_fail+=len(fails)
        print(f"[{path}] {len(items)} items - {dict(by_sub)}")
        if not fails:
            print(f" PASS - every expected answer recomputes correctly.\n")
        else:
            print(f"{len(fails)} MISMATCH(es):")
            for iid,msg in fails:
                print(f"    [{iid}] {msg}")
            print()

    print(f"=== TOTAL: {grand_total} checked, {grand_fail} problems ===")
    if grand_fail:
        sys.exit(1)

if __name__=="__main__":
    main()
