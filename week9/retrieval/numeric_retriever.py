"""
Numeric retrieval — Phase: retrieval layer, numeric path.
 
This is the first slice of the retrieval layer. It turns a routing decision
(NUMERIC) plus a resolved company into actual figures from facts.sqlite.
 
Ownership boundaries (unchanged from the classification layer):
  - route()   owns question TYPE + parses concept/years   -> numeric_part
  - resolve() owns COMPANY resolution                     -> tickers
  - THIS module owns: compose those two into one normalized query object,
    then run parameterized SQL and return STRUCTURED facts (or an honest
    no_data decline). It never re-parses concept/year and never re-resolves
    companies — single source of truth for each.
 
Contract returned by numeric_retrieve():
  {
    "status": "ok" | "no_data" | "not_numeric" | "blocked",
    "results": [ {ticker, concept, fiscal_year, value, unit,
                  period_end, entity_name}, ... ],   # ok / partial
    "missing": [ {ticker, concept, fiscal_year}, ... ],  # no_data cells
    "query":   <normalized query object>,
  }
 
Design decisions locked earlier:
  * Honest decline: a valid ticker whose (concept, fiscal_year) has no row
    returns a structured no_data entry, NOT an empty list and NOT a guessed
    nearest year. Consistent with the gate's reject posture.
  * Structured output (not a formatted string) so the hybrid path can stitch
    numbers with prose, and answer-gen owns phrasing.
  * Parameterized SQL: ticker comes from resolve(), but concept/year originate
    in user input, so every value is bound, never string-built.
"""

import sqlite3

KNOWN_CONCEPTS={"net_income","total_assets","revenue"}

def build_query(route_out,resolve_out,raw_query=""):
    np=(route_out or {}).get("numeric_part") or {}
    return {
        "route":(route_out or {}).get("route"),
        "tickers":list(resolve_out.get("tickers",[]) or []),
        "concept":np.get("concept"),
        "fiscal_years":list(np.get("years",[]) or []),
        "raw_query":raw_query,
        "resolution":resolve_out,
    }


def _query_one(cur,ticker,concept,fiscal_year):
    cur.execute(
        """
        SELECT value,unit,period_end,entity_name,form FROM facts 
        WHERE ticker=? AND concept=? AND fiscal_year=? 
        """,
        (ticker,concept,fiscal_year),
    )

    return cur.fetchone()

def numeric_retrieve(nq,db_path):
    
    if nq.get("route")!="NUMERIC":
        return {"status":"not_numeric","results":[],"missing":[],"query":nq}
    if nq["resolution"].get("status")!="resolved" or not nq["tickers"]:
        return {"status":"blocked","results":[],"missing":[],"query":nq}

    concept=nq.get("concept")
    if concept not in KNOWN_CONCEPTS:
        return {
            "status":"no_data",
            "results":[],
            "missing":[{"ticker":t,"concept":concept,"fiscal_year":y}
                        for t in nq["tickers"] for y in (nq["fiscal_years"] or [None])],
            "query":nq,
        }
    
    results,missing=[],[]
    con=sqlite3.connect(db_path)
    try:
        cur=con.cursor()
        years=nq["fiscal_years"] or [None]

        for ticker in nq["tickers"]:
            for fy in years:
                if fy is None:
                    missing.append({"ticker":ticker,"concept":concept,"fiscal_year":None})
                    continue
                row=_query_one(cur,ticker,concept,fy)
                if row is None:
                    missing.append({"ticker":ticker,"concept":concept,"fiscal_year":fy})
                else:
                    value,unit,period_end,entity_name,form =row
                    results.append({
                        "ticker":ticker,"concept":concept,"fiscal_year":fy,
                        "value":value,"unit":unit,"period_end":period_end,
                        "entity_name":entity_name,"form":form,
                    })
    finally:
        con.close()
    
    if results and not missing:
        status="ok"
    elif results and missing:
        status="partial"
    else:
        status="no_data"
    return {"status":status,"results":results,"missing":missing,"query":nq}


