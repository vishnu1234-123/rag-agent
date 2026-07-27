"""
Load XBRL facts into SQLite — the numeric query path and ground-truth store.

    python load_facts.py
"""

import sqlite3
import time
from pathlib import Path
from xbrl_companyfacts import fetch_by_ticker,get_all_annual_values

DB=Path("data/facts.sqlite")
YEARS_TO_KEEP=5
TICKERS = ["AAPL","AMZN","BA","BAC","BRK-B","CVX","GOOGL","JNJ","JPM","KO",
           "META","MSFT","NVDA","PG","T","TSLA","UNH","V","WMT","XOM"]
CONCEPTS = ["revenue", "net_income", "total_assets"]

SCHEMA="""
CREATE TABLE IF NOT EXISTS facts(
    ticker TEXT NOT NULL,
    concept TEXT NOT NULL,
    value REAL NOT NULL,
    unit TEXT,
    period_end TEXT NOT NULL,
    fiscal_year INTEGER,
    form TEXT,
    source_tag TEXT,
    entity_name TEXT,
    PRIMARY KEY (ticker,concept,period_end)
);

CREATE INDEX IF NOT EXISTS idx_facts_ticker ON facts(ticker);
CREATE INDEX IF NOT EXISTS idx_facts_concept ON facts(concept);
"""

def main():
    DB.parent.mkdir(parents=True,exist_ok=True)
    conn=sqlite3.connect(DB)
    conn.executescript(SCHEMA)
    conn.execute("DELETE FROM facts")

    rows=0
    for ticker in TICKERS:
        facts=fetch_by_ticker(ticker)
        if not facts:
            print(f"    {ticker:<6} SKIPPED (no data)")
            continue
        entity=facts.get("entityName")
        for concept in CONCEPTS:
            vals=get_all_annual_values(facts,concept)
            if YEARS_TO_KEEP:
                vals=vals[:YEARS_TO_KEEP]
            if not vals:
                print(f"    {ticker:<6} {concept} : NOT FOUND")
                continue
            for v in vals:
                conn.execute(
                    """ INSERT OR REPLACE INTO facts
                    (ticker,concept,value,unit,period_end,
                    fiscal_year,form,source_tag,entity_name)
                    VALUES(?,?,?,?,?,?,?,?,?)""",
                    (ticker,concept,v["val"],v.get("unit"),v["end"],
                     int(v["end"][:4]),v.get("form"),v.get("_source_tag"),entity),
                )
                rows+=1
        print(f"    {ticker:<6} loaded")
        time.sleep(0.2)
    conn.commit()
    stored=conn.execute("SELECT COUNT(*) FROM facts").fetchone()[0]
    conn.close()
    print(f"\nloaded {rows} rows, {stored} in db")
    assert stored==rows,"rows count mismatch"
    print("FACTS LOADED")

if __name__=="__main__":
    main()
