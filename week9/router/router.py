"""
Three-tier query router.

Routes a question to one of: NUMERIC | CONCEPTUAL | HYBRID | REJECT.

Tier 1 (rules): unambiguous single-signal questions decide instantly, no LLM.
Tier 2 (rules): questions with BOTH signals, or out-of-corpus, are detected and
                escalated — the rules deliberately refuse to guess on these.
Tier 3 (LLM):   the ambiguous remainder is classified by an LLM that returns a
                STRUCTURED decomposition, so a HYBRID is split into a numeric
                sub-query and a prose sub-query that both run downstream.

The LLM tier is cached by a hash of the (normalized) question, so repeated
questions never re-hit the API. That cache is where Redis/GPTCache plugs in;
here it's an in-process dict with the same interface so it's swappable.
"""

import hashlib
import json
import os
import re

from signals import (
    has_numeric_signal, has_prose_signal,
    has_out_of_range_year, numeric_ask_unsupported_concept,
    extract_years, extract_concept,
)

ROUTES = {"NUMERIC", "CONCEPTUAL", "HYBRID", "REJECT"}


# --- Cache (swap this dict for Redis/GPTCache later; same get/set contract) ---
class _MemoryCache:
    def __init__(self):
        self._d = {}

    def get(self, key):
        return self._d.get(key)

    def set(self, key, value):
        self._d[key] = value


_CACHE = _MemoryCache()


def _cache_key(q):
    norm = re.sub(r"\s+", " ", q.strip().lower())
    return "route:" + hashlib.sha1(norm.encode()).hexdigest()


def _decompose(q):
    """
    Structured extraction the router legitimately needs: concept and years.
    Tickers are intentionally NOT extracted here — company resolution is the
    retrieval gate's job. The router emits concept + years; the gate resolves
    the company from names/tickers/context.
    """
    return {
        "concept": extract_concept(q),
        "years": extract_years(q),
    }


# --- Tier 3: LLM classifier --------------------------------------------------
LLM_SYSTEM = """You classify financial-analysis questions for a retrieval system \
covering 20 large US public companies' SEC filings. Return ONLY a JSON object, \
no prose, no markdown fences.

Routes:
- NUMERIC: asks for an exact figure or numeric comparison (revenue, net income, \
total assets) that comes from a numbers database.
- CONCEPTUAL: asks for narrative/explanation from filing text (strategy, risks, \
reasons, descriptions) with no numeric answer required.
- HYBRID: asks for BOTH a number/comparison AND the narrative reasons behind it.
- REJECT: asks about a company NOT in the corpus, an unavailable year, or is \
otherwise unanswerable from these filings.

For HYBRID, fill both numeric_part and prose_part. For NUMERIC fill numeric_part. \
For CONCEPTUAL fill prose_part. For REJECT set reason.

Return JSON exactly of shape:
{"route": "...", "numeric_part": {"concept": "...", "tickers": [...], "years": [...]} or null,
 "prose_part": {"theme": "...", "tickers": [...]} or null, "reason": "..." or null}"""


def _llm_classify(q, client, model):
    resp = client.chat.completions.create(
        model=model,
        temperature=0,
        messages=[
            {"role": "system", "content": LLM_SYSTEM},
            {"role": "user", "content": q},
        ],
    )
    raw = resp.choices[0].message.content.strip()
    raw = re.sub(r"^```(?:json)?|```$", "", raw).strip()
    data = json.loads(raw)
    if data.get("route") not in ROUTES:
        # Defensive: if the model returns something odd, fall back to HYBRID
        # (the safest over-answer) rather than crashing.
        data["route"] = "HYBRID"
    return data


_SECOND_CLAUSE = re.compile(
    r",?\s*and\s+(?:what|how|why|which|whether)\b|"
    r";\s*(?:which|what|how|why)\b|"
    r"\band\s+what\s+(?:reasons?|factors?|explanations?|insights?|drivers?)\b|"
    r"\band\s+how\s+(?:did|does|do)\b",
    re.IGNORECASE,
)


_NARRATIVE_CONTEXT = re.compile(
    r"\bas described\b|\bin the filing\b|\bin its filing\b|\bpolicy\b|"
    r"\brealignment\b|\bpurpose of\b|\blimitations? of\b|\bmentioned\b|"
    r"\bidentif(?:y|ies|ied)\b|\bconsider(?:s|ed)?\b|\bdisclos|"
    r"\baccording to (?:the|its)\b|\bin their\b|\bin the report\b",
    re.IGNORECASE,
)


def _has_narrative_context(q):
    """
    True if the question references the filing text or a described policy/
    concept — signalling a PROSE question even when no classic prose stem
    (how/why/describe) is present. Used to stop the unsupported-concept reject
    gate from wrongly rejecting narrative questions that happen to mention a
    numeric-adjacent word.
    """
    return bool(_NARRATIVE_CONTEXT.search(q))


def route(q, client=None, model="gpt-4o-mini", use_llm=True):
    """
    Route a single question. Returns a dict:
        {"route": ..., "tier": 1|2|3, "numeric_part": ..., "prose_part": ...,
         "reason": ..., "cached": bool}

    If use_llm is False, Tier 3 is skipped and ambiguous questions get a
    deterministic best-effort route (both-signals -> HYBRID, neither -> REJECT).
    This lets the rule core be tested with no API key.
    """
    ent = _decompose(q)

    # --- Reject gates: ONLY company-INDEPENDENT rejects live here. ---
    # The router classifies question TYPE; it does NOT resolve companies.
    # Company-based rejection (out-of-corpus, no-company, generalized query,
    # typos) is the RETRIEVAL GATE's job, because that layer owns the corpus
    # and can resolve names/tickers/context. A question with no named company
    # is NOT rejected here — it may be answerable from session context
    # ("what was revenue in 2024?" with Apple in context), which only the gate
    # knows. So the router rejects only what's unanswerable regardless of
    # company: an impossible year, or an unsupported concept asked as a number.
    def _reject(reason):
        return {"route": "REJECT", "tier": 2, "numeric_part": None,
                "prose_part": None, "reason": reason, "cached": False}

    # Gate A: names a year, none in the corpus fiscal range (company-independent).
    if has_out_of_range_year(q):
        return _reject("year outside corpus range")
    # Gate B: numeric ask about a concept the fact store doesn't hold, with no
    # narrative framing (company-independent). Prose about the concept is fine.
    if numeric_ask_unsupported_concept(q) and not _has_narrative_context(q):
        return _reject("numeric concept not available")

    num = has_numeric_signal(q)
    prose = has_prose_signal(q)

    # --- Structural escalation (before Tier 1) ---
    # A numeric question with a SECOND CLAUSE asking for reasons ("...and what
    # reasons did each give", "...; which had the higher value, and what insights
    # did they offer") is a hybrid even if the prose vocabulary wasn't detected.
    # The second clause is the real hybrid signature — it's the part asking for
    # narrative alongside the number.
    #
    # NOTE: we deliberately do NOT escalate merely because two companies appear.
    # Most two-company numeric questions are pure COMPARISONS ("which is larger,
    # JPM or Apple?"), not hybrids — escalating those just hands a question the
    # rules had right to the LLM, which may fumble it. The distinguishing feature
    # of a hybrid is the reasons-clause, not the company count.
    second_clause = bool(_SECOND_CLAUSE.search(q))
    if num and second_clause:
        num = prose = True  # force the both-signals escalation path below

    # --- Tier 1: exactly one signal -> decide instantly ---
    if num and not prose:
        return {"route": "NUMERIC", "tier": 1,
                "numeric_part": {"concept": ent["concept"],
                                 "tickers": [],
                                 "years": ent["years"]},
                "prose_part": None, "reason": None, "cached": False}

    if prose and not num:
        return {"route": "CONCEPTUAL", "tier": 1,
                "numeric_part": None,
                "prose_part": {"theme": q, "tickers": []},
                "reason": None, "cached": False}

    # --- Tier 2b: both signals (or neither) -> escalate to LLM ---
    cached = _CACHE.get(_cache_key(q))
    if cached is not None:
        out = dict(cached)
        out["cached"] = True
        return out

    if not use_llm or client is None:
        # Deterministic fallback for offline testing.
        # PRINCIPLE: REJECT is a positive assertion of unanswerability, made
        # only by the certain reject gates above. Down here the rules are
        # UNSURE — so escalate, never reject. With no LLM available offline,
        # we approximate the escalation with a best-effort route:
        #   both signals -> HYBRID; otherwise -> CONCEPTUAL (prose is the safe
        #   default, since an unclear question is far more often a narrative
        #   one than a genuine reject, and CONCEPTUAL retrieval can still find
        #   or gracefully miss). The LLM tier, when on, replaces this guess.
        if num and prose:
            out = {"route": "HYBRID", "tier": 2,
                   "numeric_part": {"concept": ent["concept"],
                                    "tickers": [],
                                    "years": ent["years"]},
                   "prose_part": {"theme": q, "tickers": []},
                   "reason": None}
        else:
            out = {"route": "CONCEPTUAL", "tier": 2,
                   "numeric_part": None,
                   "prose_part": {"theme": q, "tickers": []},
                   "reason": None}
        out["cached"] = False
        return out

    data = _llm_classify(q, client, model)
    data["tier"] = 3
    _CACHE.set(_cache_key(q), data)
    out = dict(data)
    out["cached"] = False
    return out