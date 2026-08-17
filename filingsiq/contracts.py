"""
contracts.py — the typed spine of the FilingsIQ pipeline.

Every stage imports its input/output types from here. This replaces the
sys.path.insert coupling: stages depend on these CONTRACTS, not on each other's
file locations. It also makes the year/concept/operation bugs structurally
impossible — those values are REQUIRED fields carried forward, never re-parsed.

Enums are plain string constants (JSON-friendly, matches existing string dicts).

Corpus invariants:
  - Supported concepts: revenue | net_income | total_assets
  - Corpus years:       2021..2025 (numeric); prose = 2025 filing only
  - Operations:         point | delta | trend | gap | growth_compare | rank
"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Optional

CONCEPTS = ("revenue", "net_income", "total_assets")
OPERATIONS = ("point", "delta", "trend", "gap", "growth_compare", "rank")
KINDS = ("numeric", "prose")
ROUTES = ("NUMERIC", "CONCEPTUAL", "HYBRID", "REJECT")

CORPUS_YEARS = frozenset(range(2021, 2026))
PROSE_YEAR = 2025


@dataclass
class RouteResult:
    route: str
    concept: Optional[str] = None
    years: list[int] = field(default_factory=list)
    operation: Optional[str] = None
    reason: Optional[str] = None
    tier: Optional[int] = None


@dataclass
class Resolution:
    status: str
    tickers: list[str] = field(default_factory=list)
    names: list[str] = field(default_factory=list)
    suggestion: Optional[tuple] = None


@dataclass
class SubQuestion:
    """
    text is the CLEAN semantic query (no year range stuffed in, no operation
    words). concept/years/operation/ticker are STRUCTURED metadata carried from
    the decomposer — NOT re-parsed downstream. years is a retrieval FILTER,
    never injected into the embedding query.
    """
    text: str
    kind: str
    ticker: Optional[str] = None
    concept: Optional[str] = None
    years: list[int] = field(default_factory=list)
    operation: Optional[str] = None


@dataclass
class QueryPlan:
    original_question: str
    operation: Optional[str]
    sub_questions: list[SubQuestion] = field(default_factory=list)
    rejected: bool = False
    reject_reason: Optional[str] = None


@dataclass
class NumericResult:
    subq: str
    kind: str
    status: str
    value: Optional[float] = None
    delta: Optional[float] = None
    ticker: Optional[str] = None
    concept: Optional[str] = None
    detail: dict = field(default_factory=dict)


@dataclass
class ProseContext:
    parents: list[dict]
    query: str


@dataclass
class Answer:
    subq: str
    text: str
    declined: bool
    reason: Optional[str] = None
    tickers: list[str] = field(default_factory=list)


@dataclass
class HybridAnswer:
    question: str
    synthesis: str
    numeric_results: list[NumericResult] = field(default_factory=list)
    prose_answers: list[Answer] = field(default_factory=list)
    declined: bool = False
    reason: Optional[str] = None


def is_supported_concept(c: Optional[str]) -> bool:
    return c in CONCEPTS

def is_corpus_year(y: int) -> bool:
    return y in CORPUS_YEARS

def prose_needs_missing_filing(years: list[int]) -> bool:
    """
    True if a PROSE sub-question needs a filing that doesn't exist.
    Prose corpus is the 2025 filing only. A multi-year 'why' is fine (answered
    from the 2025 filing's retrospective). Reject iff there are years and none
    is 2025.
    """
    return bool(years) and PROSE_YEAR not in years
