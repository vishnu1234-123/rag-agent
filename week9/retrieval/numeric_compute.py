"""
Numeric compute layer — runtime, deterministic, no LLM.
 
Turns retrieved rows into computed answers. Operation is chosen by:
  1. detect_operation(raw_query): wording hint (gap / growth_compare / rank / None)
  2. reconciled against the ACTUAL company count (a hint only applies if the shape
     supports it — "grow" in a single-company question is a trend, not a comparison)
  3. anything not explicitly tagged falls back to SHAPE inference:
        1co/1yr -> point ; 1co/Nyr -> delta|trend ; Nco/1yr -> ranking
 
This explicit-operation-tag pattern (rules now, LLM-fallback seam later) is the
robust successor to pure shape-inference — reused for word-framed questions when
the eval grows to include them.
"""

_GAP_MARKERS    = ("how much larger", "how much bigger", "how much more",
                   "how much smaller", "how much less", "difference between",
                   "gap between", "larger than", "bigger than")
_GROWTH_MARKERS = ("grew faster", "grow faster", "which grew", "growth",
                   "faster", "fastest")
_RANK_MARKERS   = ("highest", "largest", "biggest", "most", "lowest",
                   "smallest", "least", "rank", "which had the")

def detect_operation(raw_query):
    q=(raw_query or "").lower()
    if any(m in q for m in _GAP_MARKERS):
        return "gap"
    if any(m in q for m in _GROWTH_MARKERS):
        return "growth_compare"
    if any(m in q for m in _RANK_MARKERS):
        return "rank"
    return None

def _reconcile(op,n_companies):
    if op in ("gap","growth_compare","rank") and n_companies<2:
        return None
    return op

def _by_company(results):
    out={}
    for r in results:
        out.setdefault(r["ticker"],{})[r["fiscal_year"]]=r["value"]
    return out

def compute(retrieval_out):
    status=retrieval_out.get("status")
    results=retrieval_out.get("results",[])
    if status not in ("ok","partial") or not results:
        return {"kind":"none","status":status,
                "missing":retrieval_out.get("missing",[]),
                "retrieval":retrieval_out}
    by_co=_by_company(results)
    n_companies=len(by_co)
    max_years_per_co=max(len(yv) for yv in by_co.values())
    concept=results[0]["concept"]

    op=_reconcile(detect_operation(retrieval_out.get("query",{}).get("raw_query","") if isinstance(retrieval_out.get("query"),dict) else ""),n_companies)

    if op=="gap" and n_companies==2:
        items=[(t,sorted(yv)[-1],yv[sorted(yv)[-1]]) for t,yv in by_co.items()]
        items.sort(key=lambda x:x[2] , reverse=True)
        (t1,y1,v1),(t2,y2,v2)=items[0],items[1]
        return {"kind":"gap","status":status,"larger":t1,"smaller":t2,
                "gap":v1-v2,"values":{t1:v1,t2:v2},
                "concept":concept,"retrieval":retrieval_out}
    
    if op=="growth_compare" and n_companies>=2:
        res=[]
        for t,yv in by_co.items():
            ys=sorted(yv)
            v0,v1=yv[ys[0]],yv[ys[-1]]
            pct=(v1-v0)/abs(v0)*100 if v0 else float("inf")
            res.append((t,pct,v0,v1))
        res.sort(key=lambda x:x[1], reverse=True)
        return {"kind":"growth_compare","status":status,"winner":res[0][0],
                "growth":{t:round(p,1) for t,p,_,_ in res},
                "concept":concept,"retrieval":retrieval_out}


    if n_companies>=2 and max_years_per_co>=2:
        return {
            "kind": "unsupported",
            "status": "ambiguous",
            "reason": "compound operation (multi-company multi-year) not supported",
            "n_companies": n_companies,
            "max_years_per_company": max_years_per_co,
            "concept": results[0]["concept"],
            "retrieval": retrieval_out,
        }
    
    if n_companies>=2:
        ranked=[]
        for tkr,yv in by_co.items():
            yr=sorted(yv)[-1]
            ranked.append((tkr,yr,yv[yr]))
        ranked.sort(key=lambda x:x[2],reverse=True)
        winner=ranked[0]
        return{
            "kind":"ranking",
            "status":status,
            "winner_ticker":winner[0],
            "winner_value":winner[2],
            "ordered":ranked,
            "concept":results[0]["concept"],
            "retrieval":retrieval_out,
        }
    
    tkr,yv=next(iter(by_co.items()))
    years=sorted(yv)
    concept=results[0]["concept"]
    if len(years)==1:
        y=years[0]
        return {"kind": "point", "status": status, "ticker": tkr,
                "concept": concept, "fiscal_year": y, "value": yv[y],
                "retrieval": retrieval_out}
    
    y1,y2=years[0],years[-1]
    delta=yv[y2]-yv[y1]
    result={
        "status":status,"ticker":tkr,"concept":concept,
        "from_year":y1,"to_year":y2,
        "from_value":yv[y1],"to_value":yv[y2],
        "delta":delta,
        "retrieval":retrieval_out,
    }

    if len(years)==2:
        result["kind"]="delta"
    else:
        result["kind"]="trend"
        result["direction"]="grew" if delta > 0 else ("shrank" if delta<0 else "flat")
        result["series"]=[(y,yv[y]) for y in years] 
    return result


if __name__ == "__main__":
    # local smoke test — hand-built retrieval_out shapes
    point = {"status": "ok", "results": [
        {"ticker": "UNH", "concept": "net_income", "fiscal_year": 2025, "value": 12056000000.0}]}
    yoy = {"status": "ok", "results": [
        {"ticker": "BA", "concept": "revenue", "fiscal_year": 2021, "value": 62286000000.0},
        {"ticker": "BA", "concept": "revenue", "fiscal_year": 2022, "value": 66608000000.0}]}
    trend = {"status": "ok", "results": [
        {"ticker": "AAPL", "concept": "net_income", "fiscal_year": 2021, "value": 94680000000.0},
        {"ticker": "AAPL", "concept": "net_income", "fiscal_year": 2023, "value": 96995000000.0},
        {"ticker": "AAPL", "concept": "net_income", "fiscal_year": 2025, "value": 112010000000.0}]}
    rank = {"status": "ok", "results": [
        {"ticker": "NVDA", "concept": "total_assets", "fiscal_year": 2023, "value": 41182000000.0},
        {"ticker": "TSLA", "concept": "total_assets", "fiscal_year": 2023, "value": 106618000000.0},
        {"ticker": "XOM", "concept": "total_assets", "fiscal_year": 2023, "value": 376317000000.0}]}
 
    # compound shape: 2 companies AND 2 years -> must be refused
    compound = {"status": "ok", "results": [
        {"ticker": "MSFT", "concept": "total_assets", "fiscal_year": 2022, "value": 364840000000.0},
        {"ticker": "MSFT", "concept": "total_assets", "fiscal_year": 2025, "value": 533898000000.0},
        {"ticker": "NVDA", "concept": "total_assets", "fiscal_year": 2022, "value": 44187000000.0},
        {"ticker": "NVDA", "concept": "total_assets", "fiscal_year": 2025, "value": 111601000000.0}]}
 
    for name, r in [("point", point), ("yoy", yoy), ("trend", trend),
                    ("rank", rank), ("compound", compound)]:
        c = compute(r)
        print(f"{name:9} -> kind={c['kind']:12}", {k: v for k, v in c.items()
              if k in ("value", "delta", "direction", "winner_ticker", "reason")})
