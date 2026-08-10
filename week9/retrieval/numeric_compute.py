"""
Numeric compute layer — runtime, deterministic, no LLM.
 
Sits between numeric retrieval and answer generation. Retrieval fetches raw
rows from facts.sqlite; THIS layer turns those rows into the actual computed
answer (a value, a delta, a trend, or a ranking).
 
Key principle: this runs at RUNTIME, where there is no `subtype` label. It
infers WHICH computation to run from the SHAPE of the retrieved rows, not from
any eval metadata:
 
    1 company, 1 year            -> point     (the value itself)
    1 company, 2 years           -> delta     (y2 - y1)
    1 company, 3+ years          -> trend     (delta + direction over the span)
    N companies, 1 year          -> ranking   (argmax over companies)
 
Arithmetic mirrors week8/eval/gen_numeric_eval.py (gen_point/yoy/trend/ranking)
so the runtime reproduces exactly what the generator computed as ground truth.
 
Returns a structured result; answer-gen owns phrasing later.
"""

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
