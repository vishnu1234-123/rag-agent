"""
Numeric eval-set generator for FilingsIQ.

Builds numeric evaluation questions DIRECTLY from data/facts.sqlite, so every
answer is correct by construction — no human transcription, no LLM guessing.
Each question carries full provenance (the source rows it was built from) and
an expected_route so the eval can also grade the query router later.

Four sub-types:
  point   — "What was {company}'s {concept} in {year}?"          -> exact value
  yoy     — "How much did {company}'s {concept} change {y1}->{y2}?" -> delta
  trend   — "Did {company}'s {concept} grow or shrink {y1}->{y2}?"  -> direction
  ranking — "Which of {A,B,C} had the highest {concept} in {year}?" -> argmax

Design choices that prevent silently-wrong ground truth:
  - Per-ticker year coverage is read from the DB, never assumed to be 5.
  - Ranking questions pin an explicit year and only include tickers that
    actually have a row for that (ticker, concept, year) — never compares
    across mismatched fiscal periods (NVDA/WMT end in Jan, so their FY2026
    is real but must not be compared to others' FY2025).
  - Values are raw USD in the DB; formatted to $X.XXB / $X.XXT for questions,
    but expected_value stays raw for exact machine checking.

Usage:
    python gen_numeric_eval.py --db data/facts.sqlite --out numeric_eval.json
    python gen_numeric_eval.py --db data/facts.sqlite --seed 7 --n-point 25 ...
"""

import argparse
import json
import random
import sqlite3
from collections import defaultdict

# Human-readable names so questions don't say "AAPL" like a robot.
COMPANY_NAMES = {
    "AAPL": "Apple", "AMZN": "Amazon", "BA": "Boeing", "BAC": "Bank of America",
    "BRK-B": "Berkshire Hathaway", "CVX": "Chevron", "GOOGL": "Alphabet",
    "JNJ": "Johnson & Johnson", "JPM": "JPMorgan Chase", "KO": "Coca-Cola",
    "META": "Meta", "MSFT": "Microsoft", "NVDA": "NVIDIA", "PG": "Procter & Gamble",
    "T": "AT&T", "TSLA": "Tesla", "UNH": "UnitedHealth", "V": "Visa",
    "WMT": "Walmart", "XOM": "ExxonMobil",
}

CONCEPT_PHRASE = {
    "revenue": "revenue",
    "net_income": "net income",
    "total_assets": "total assets",
}


def fmt_usd(value):
    """Raw USD float -> compact human string. 416161000000 -> '$416.16B'."""
    v = float(value)
    sign = "-" if v < 0 else ""
    a = abs(v)
    if a >= 1e12:
        return f"{sign}${a/1e12:.2f}T"
    if a >= 1e9:
        return f"{sign}${a/1e9:.2f}B"
    if a >= 1e6:
        return f"{sign}${a/1e6:.2f}M"
    return f"{sign}${a:,.0f}"


def load_facts(db_path):
    con = sqlite3.connect(db_path)
    con.row_factory = sqlite3.Row
    rows = con.execute(
        "SELECT ticker, concept, value, unit, period_end, fiscal_year, "
        "form, source_tag FROM facts"
    ).fetchall()
    con.close()
    # index: facts[ticker][concept][fiscal_year] = row dict
    facts = defaultdict(lambda: defaultdict(dict))
    for r in rows:
        facts[r["ticker"]][r["concept"]][r["fiscal_year"]] = dict(r)
    return facts


def provenance(row):
    """Minimal auditable fingerprint of a source row."""
    return {
        "ticker": row["ticker"], "concept": row["concept"],
        "fiscal_year": row["fiscal_year"], "value": row["value"],
        "period_end": row["period_end"], "source_tag": row["source_tag"],
    }


def gen_point(facts, rng, n):
    """Point lookups: exact single value."""
    pool = []
    for t, concepts in facts.items():
        for c, years in concepts.items():
            for y, row in years.items():
                pool.append((t, c, y, row))
    rng.shuffle(pool)
    out = []
    for t, c, y, row in pool[:n]:
        out.append({
            "id": f"num_point_{t}_{c}_{y}",
            "category": "numeric",
            "subtype": "point",
            "expected_route": "NUMERIC",
            "question": f"What was {COMPANY_NAMES[t]}'s {CONCEPT_PHRASE[c]}"
                        f" in fiscal year {y}?",
            "expected_value": row["value"],
            "expected_answer": fmt_usd(row["value"]),
            "source_rows": [provenance(row)],
        })
    return out


def gen_yoy(facts, rng, n):
    """Year-over-year absolute change between two consecutive years."""
    pool = []
    for t, concepts in facts.items():
        for c, years in concepts.items():
            ys = sorted(years)
            for i in range(len(ys) - 1):
                y1, y2 = ys[i], ys[i + 1]
                pool.append((t, c, y1, y2, years[y1], years[y2]))
    rng.shuffle(pool)
    out = []
    for t, c, y1, y2, r1, r2 in pool[:n]:
        delta = r2["value"] - r1["value"]
        direction = "increased" if delta > 0 else "decreased"
        out.append({
            "id": f"num_yoy_{t}_{c}_{y1}_{y2}",
            "category": "numeric",
            "subtype": "yoy",
            "expected_route": "NUMERIC",
            "question": f"By how much did {COMPANY_NAMES[t]}'s"
                        f" {CONCEPT_PHRASE[c]} change from fiscal {y1} to {y2}?",
            "expected_value": delta,
            "expected_answer": f"{direction} by {fmt_usd(abs(delta))}"
                               f" ({fmt_usd(r1['value'])} -> {fmt_usd(r2['value'])})",
            "source_rows": [provenance(r1), provenance(r2)],
        })
    return out


def gen_trend(facts, rng, n):
    """Direction of change across a multi-year span (first vs last available)."""
    pool = []
    for t, concepts in facts.items():
        for c, years in concepts.items():
            ys = sorted(years)
            if len(ys) >= 3:  # only ask trend where there's a real span
                pool.append((t, c, ys[0], ys[-1], years[ys[0]], years[ys[-1]]))
    rng.shuffle(pool)
    out = []
    for t, c, y1, y2, r1, r2 in pool[:n]:
        delta = r2["value"] - r1["value"]
        direction = "grew" if delta > 0 else "shrank"
        pct = (delta / r1["value"] * 100) if r1["value"] else 0
        out.append({
            "id": f"num_trend_{t}_{c}_{y1}_{y2}",
            "category": "numeric",
            "subtype": "trend",
            "expected_route": "NUMERIC",
            "question": f"Did {COMPANY_NAMES[t]}'s {CONCEPT_PHRASE[c]} grow or"
                        f" shrink from fiscal {y1} to {y2}?",
            "expected_value": delta,
            "expected_answer": f"{direction} ({pct:+.1f}%,"
                               f" {fmt_usd(r1['value'])} -> {fmt_usd(r2['value'])})",
            "source_rows": [provenance(r1), provenance(r2)],
        })
    return out


def gen_ranking(facts, rng, n, group_size=3):
    """Argmax over a small group, for a pinned year all members actually have."""
    out = []
    attempts = 0
    seen = set()
    tickers = list(facts.keys())
    while len(out) < n and attempts < n * 40:
        attempts += 1
        concept = rng.choice(["revenue", "net_income", "total_assets"])
        group = tuple(sorted(rng.sample(tickers, group_size)))
        # years for which ALL group members have this concept
        common_years = None
        ok = True
        for t in group:
            ys = set(facts[t].get(concept, {}).keys())
            if not ys:
                ok = False
                break
            common_years = ys if common_years is None else (common_years & ys)
        if not ok or not common_years:
            continue
        year = rng.choice(sorted(common_years))
        key = (concept, group, year)
        if key in seen:
            continue
        seen.add(key)
        rows = [facts[t][concept][year] for t in group]
        winner = max(rows, key=lambda r: r["value"])
        names = ", ".join(COMPANY_NAMES[t] for t in group)
        out.append({
            "id": f"num_rank_{concept}_{'_'.join(group)}_{year}",
            "category": "numeric",
            "subtype": "ranking",
            "expected_route": "NUMERIC",
            "question": f"Which of these had the highest {CONCEPT_PHRASE[concept]}"
                        f" in fiscal year {year}: {names}?",
            "expected_value": winner["ticker"],
            "expected_answer": f"{COMPANY_NAMES[winner['ticker']]}"
                               f" ({fmt_usd(winner['value'])})",
            "source_rows": [provenance(r) for r in rows],
        })
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default="data/facts.sqlite")
    ap.add_argument("--out", default="numeric_eval.json")
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--n-point", type=int, default=22)
    ap.add_argument("--n-yoy", type=int, default=14)
    ap.add_argument("--n-trend", type=int, default=12)
    ap.add_argument("--n-ranking", type=int, default=12)
    args = ap.parse_args()

    rng = random.Random(args.seed)
    facts = load_facts(args.db)

    items = []
    items += gen_point(facts, rng, args.n_point)
    items += gen_yoy(facts, rng, args.n_yoy)
    items += gen_trend(facts, rng, args.n_trend)
    items += gen_ranking(facts, rng, args.n_ranking)

    with open(args.out, "w") as f:
        json.dump(items, f, indent=2)

    by_sub = defaultdict(int)
    for it in items:
        by_sub[it["subtype"]] += 1
    print(f"[done] wrote {len(items)} numeric questions -> {args.out}")
    for k in ("point", "yoy", "trend", "ranking"):
        print(f"  {k:8} {by_sub[k]}")
    print("\n--- 6 samples ---")
    for it in rng.sample(items, min(6, len(items))):
        print(f"\nQ: {it['question']}")
        print(f"A: {it['expected_answer']}")


if __name__ == "__main__":
    main()