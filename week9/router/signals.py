"""
Signal detection for the query router — question TYPE only.

Pure, deterministic, COMPANY-AGNOSTIC functions. These decide whether a question
is numeric / conceptual / hybrid in shape, and catch the two company-INDEPENDENT
rejects (impossible year, unsupported concept asked as a number).

Company resolution — which company, is it in corpus, typo correction — is NOT
here. It lives in gate/company_resolution.py and runs at the retrieval gate,
because that layer owns the corpus and can use session context. The router
classifies the question; the gate resolves the company.

Design note: prose-side detection is intentionally generous. A false escalation
to the LLM costs a fraction of a cent; a missed hybrid gives the user a
confidently wrong half-answer. When in doubt, flag the signal.
"""

import re

# --- Numeric signals ---------------------------------------------------------
# The three financial concepts the numeric store (facts.sqlite) holds. Note:
# this is a ROUTING signal (does the question mention a numeric concept?), not a
# resolution — validating that a concept+company+year actually maps to a stored
# fact is the gate's job.
CONCEPT_PATTERNS = {
    "revenue":       r"\brevenues?\b|\bnet sales\b|\btotal sales\b",
    "net_income":    r"\bnet income\b|\bnet earnings\b|\bprofit\b",
    "total_assets":  r"\btotal[al]* assets\b|\bbalance sheet size\b",
}

# Phrasings that ask for a number / numeric comparison / ranking.
NUMERIC_ASK = re.compile(
    r"\bhow much\b|\bwhat (?:was|is|were|are)\b|\bhow many\b|"
    r"\bwhich is (?:larger|bigger|higher|greater|smaller|lower)\b|"
    r"\bwhich .{0,40}\b(?:grew|grow|increased|declined|higher|lower|"
    r"faster|fastest|most|least|largest|biggest|highest|lowest|"
    r"smallest|greatest|greater)\b|"
    r"\b(?:highest|lowest|largest|smallest|greatest)\b|"
    r"\bcompare\b|\bcomparison\b|\bhow did .{0,30}(?:change|grow)\b",
    re.IGNORECASE,
)

YEAR = re.compile(r"\b(19|20)\d{2}\b")

# Fiscal years actually present in the corpus. Years named outside this range
# (1920, 2080) mean the data does not exist -> REJECT. Company-independent.
VALID_YEARS = set(range(2021, 2026))

# Broad detector for a year TOKEN following "fiscal year" / "year" / "in".
# Catches malformed/absurd years the strict YEAR regex misses:
#   "fiscal year 3000", "fiscal year 20255", "fiscal year 20X6", "year zero".
YEAR_TOKEN = re.compile(
    r"\b(?:fiscal\s+year|year|in|for|during|fy)\s+"
    r"([0-9]{1,5}|[0-9]{2,4}[a-z][0-9a-z]*|year\s+zero|zero)\b",
    re.IGNORECASE,
)

# --- Prose signals -----------------------------------------------------------
# Narrative / explanation phrasings, plus the (bounded) vocabulary of causation
# and explanation ("why", "drivers", "reasons behind", "narrative"). This is a
# closed linguistic set, not an open-ended phrasing list, so encoding it is
# principled rather than a treadmill.
PROSE_ASK = re.compile(
    r"\bhow does\b|\bhow do\b|\bhow might\b|\bhow have\b|\bhow could\b|"
    r"\bhow can\b|\bhow has\b|\bdescribe\b|\bdescription\b|\bwhy\b|"
    r"\breasons?\b|\bexplain\b|\bstrateg(?:y|ies)\b|\brisks?\b|"
    r"\bfactors?\b|\bdiscuss(?:es|ed)?\b|\bapproach\b|\bcite[sd]?\b|"
    r"\bwhat (?:kind|type)s? of\b|\bcharacteriz|\boutlook\b|"
    r"\bhow .{0,20}describe\b|\bqualitativ|"
    r"\bwhat challenges?\b|\bwhat consequences?\b|\bwhat potential\b|"
    r"\bwhat impact\b|\bimpact of\b|\bimpacts? (?:of|on|do|does|could|might)\b|"
    r"\bwhat contributed\b|\bcontributed to\b|\bdrivers? of\b|"
    r"\bwhat obligations?\b|\bwhat limitations?\b|\bconsequences?\b|"
    r"\bwhat significant\b|\bwhat specific\b|\bpotential (?:impact|consequence|effect)|"
    r"\bdrivers?\b|\bdrove\b|\bcontributors?\b|\bnarrative\b|\bled to\b|\bcaused?\b|\bcausing\b|"
    r"\bbehind the\b|\breasons? behind\b|\battribut|\bunderlying\b|"
    r"\bwhy did\b|\bwhy has\b|\bwhy was\b|\bwhy were\b|"
    r"\bexperienced? (?:a |an )?(?:notable |significant )?(?:increase|decrease|decline|drop|surge|growth|fluctuation)|"
    r"\bfluctuat|\bregarding the (?:increase|decrease|decline|change|drop|surge|growth)",
    re.IGNORECASE,
)


def extract_years(q):
    return sorted({int(m.group()) for m in YEAR.finditer(q)})


def extract_concept(q):
    for concept, pat in CONCEPT_PATTERNS.items():
        if re.search(pat, q, re.IGNORECASE):
            return concept
    return None


def has_numeric_signal(q):
    """
    True if the question asks for a number the fact store could return: a
    recognized concept plus either a numeric-ask/ranking phrase or a year.
    """
    if extract_concept(q) is None:
        return False
    if NUMERIC_ASK.search(q):
        return True
    if extract_years(q):
        return True
    return False


def has_prose_signal(q):
    """True if the question asks for narrative/explanation."""
    return bool(PROSE_ASK.search(q))


def has_out_of_range_year(q):
    """
    True if the question names a year that isn't a valid in-corpus year.
    Company-independent reject signal. Handles well-formed out-of-range years
    (1920, 2080) and malformed year tokens (3000, 20255, 20X6, 'year zero').
    """
    years = extract_years(q)
    if years and not any(y in VALID_YEARS for y in years):
        return True
    for m in YEAR_TOKEN.finditer(q):
        tok = m.group(1).strip().lower()
        if tok.isdigit():
            if int(tok) not in VALID_YEARS:
                return True
        else:
            return True  # non-numeric token in a year slot: "20X6", "year zero"
    return False


def numeric_ask_unsupported_concept(q):
    """
    True if the question wants a NUMBER about a concept the fact store does not
    hold (only revenue / net_income / total_assets exist). Company-independent.
    A PROSE ask about an unsupported concept is NOT flagged — the narrative may
    still be answerable from filing text.
    """
    if not NUMERIC_ASK.search(q) and not extract_years(q):
        return False
    if has_prose_signal(q):
        return False
    return extract_concept(q) is None