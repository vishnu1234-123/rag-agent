"""
Company resolution for the RETRIEVAL GATE (next phase).

This owns all company/corpus knowledge, moved out of the router's signal layer.
The router classifies question TYPE and never touches this; the gate calls it to
resolve which company a question is about and to reject company-based out-of-scope
cases.

Responsibilities (the five-case resolution):
  1. Named in-corpus company           -> resolve to ticker, retrieve.
  2. Ticker symbol (NVDA, XOM)          -> resolve to ticker, retrieve.
  3. Named out-of-corpus company        -> reject ("not in coverage").
  4. Near-miss / typo (Chevorn)         -> suggest "did you mean Chevron?".
  5. No company named                   -> use session context; if none, ask.

Also validates (gate's job, not the router's): does concept+company+year actually
map to a stored fact? "numeric keywords" != "answerable numeric question".

NOTE: this is the SEED for the next phase. The router does not import it. The
interactive parts (typo confirmation, "which company?") belong to the
conversation layer above the gate; this module provides the detection/resolution
primitives those flows call.
"""

import re
import difflib

# --- Corpus: the 20 covered companies ---------------------------------------
# ticker -> lowercased name variants that appear in questions.
CORPUS = {
    "AAPL":  {"apple"},
    "AMZN":  {"amazon"},
    "BA":    {"boeing"},
    "BAC":   {"bank of america"},
    "BRK-B": {"berkshire", "berkshire hathaway"},
    "CVX":   {"chevron"},
    "GOOGL": {"alphabet", "google"},
    "JNJ":   {"johnson & johnson", "johnson and johnson", "j&j"},
    "JPM":   {"jpmorgan", "jpmorgan chase", "jp morgan"},
    "KO":    {"coca-cola", "coca cola", "coke"},
    "META":  {"meta", "facebook"},
    "MSFT":  {"microsoft"},
    "NVDA":  {"nvidia"},
    "PG":    {"procter & gamble", "procter and gamble", "p&g"},
    "T":     {"at&t", "at & t"},
    "TSLA":  {"tesla"},
    "UNH":   {"unitedhealth", "united health"},
    "V":     {"visa"},
    "WMT":   {"walmart"},
    "XOM":   {"exxonmobil", "exxon", "exxon mobil"},
}

_NAME_TO_TICKER = []
for _tk, _names in CORPUS.items():
    for _n in _names:
        _NAME_TO_TICKER.append((_n, _tk))
_NAME_TO_TICKER.sort(key=lambda x: -len(x[0]))

VALID_TICKERS = set(CORPUS.keys())

# Common out-of-corpus names that appear in reject traps. NOT exhaustive — the
# real backstop for unknown companies is "resolves to no in-corpus ticker", not
# this list. It just gives common outsiders a clean early reject reason.
KNOWN_OUTSIDERS = {
    "pepsico", "pepsi", "netflix", "oracle", "salesforce",
    "disney", "ford", "intel", "amd", "starbucks", "nike",
    "wells fargo", "citigroup", "goldman sachs", "morgan stanley",
    "pfizer", "merck", "abbvie", "eli lilly", "shell", "bp",
    "conocophillips", "target", "lowe's", "lowes", "american express",
}


def extract_tickers(q):
    """
    Resolve in-corpus tickers from a question, matching company names ("nvidia")
    and long ticker symbols ("NVDA"). Short tickers (T, V) are deliberately NOT
    matched as bare words here — they collide with prose ("T-bills", "V-shaped")
    and are better resolved with full context at the gate.
    """
    ql = q.lower()
    found = set()
    for name, tk in _NAME_TO_TICKER:
        if name in ql:
            found.add(tk)
            ql = ql.replace(name, " ")
    for tk in VALID_TICKERS:
        if len(tk.replace("-", "")) >= 3:
            if re.search(rf"\b{re.escape(tk)}\b", q, re.IGNORECASE):
                found.add(tk)
    return sorted(found)


def extract_out_of_corpus_names(q):
    """Detect known out-of-corpus company names in the question."""
    ql = q.lower()
    return [name for name in KNOWN_OUTSIDERS if name in ql]


def is_out_of_corpus(q):
    """True if the question names a known outsider and no in-corpus company."""
    return bool(extract_out_of_corpus_names(q)) and not extract_tickers(q)


def suggest_company(q, threshold=0.6):
    """
    Return the nearest in-corpus (ticker, name) for a company-like token that
    doesn't exactly match the corpus — a 'did you mean?' suggestion for typos
    (Chevorn -> Chevron). Returns None if nothing is close enough.
    """
    candidates = re.findall(r"\b[A-Z][A-Za-z&.\-]+(?:\s+[A-Z][A-Za-z&.\-]+)*", q)
    all_names = [(n, tk) for n, tk in _NAME_TO_TICKER]
    ql = q.lower()
    best, best_score = None, 0.0
    for cand in candidates:
        cl = cand.lower()
        if cl in {"fiscal", "the company", "company"}:
            continue
        for name, tk in all_names:
            score = difflib.SequenceMatcher(None, cl, name).ratio()
            if score > best_score and score >= threshold and name not in ql:
                best_score, best = score, (tk, name)
    return best

def _company_phrases(q):
    STOP = {"what", "which", "how", "can", "could", "was", "were", "the company",
            "company", "fiscal", "in", "for"}
    spans = re.findall(r"\b[A-Z][A-Za-z&.\-]+(?:\s+[A-Z][A-Za-z&.\-]+)*", q)
    return [s for s in spans if s.lower() not in STOP]

def _is_exact_variant(phrase):
    p=phrase.lower()
    if p in {n for n,_ in _NAME_TO_TICKER}:
        return True

    if phrase.upper() in VALID_TICKERS:
        return True
    return False

def resolve(q, context_ticker=None):
    """
    The gate's main entry point (SEED — extend in next phase).
    Returns a dict describing the resolution outcome:
      {"status": "resolved", "tickers": [...]}         # 1,2: named/ticker in corpus
      {"status": "out_of_corpus", "names": [...]}      # 3: reject
      {"status": "typo", "suggestion": (tk, name)}     # 4: did you mean?
      {"status": "use_context", "ticker": context}     # 5a: no company, context supplies it
      {"status": "need_company"}                       # 5b: no company, no context -> ask

      Ordering matters: a TYPO must be caught before a partial substring match is
    accepted as a clean resolve. "JP Morgan Chse" substring-matches "jp morgan"
    -> extract_tickers returns JPM, but the phrase is NOT an exact corpus variant
    and is a near-miss for "jpmorgan chase", so it's a typo, not a resolution.
    """
    phrases=_company_phrases(q)
    tickers=extract_tickers(q)

    if tickers:
        unmatched=[p for p in phrases if not _is_exact_variant(p)]
        if not unmatched:
            return {"status":"resolved","tickers":tickers}
        
        sugg=suggest_company(q)
        if sugg:
            return {"status":"typo","suggestion":sugg}
        return {"status":"resolved","tickers":tickers}
    if is_out_of_corpus(q):
        return {"status":"out_of_corpus","names":extract_out_of_corpus_names(q)}
    sugg=suggest_company(q)
    if sugg:
        return {"status":"typo","suggestion":sugg}
    if context_ticker:
        return {"status":"use_context","ticker":context_ticker}
    return {"status":"need_company"}
    