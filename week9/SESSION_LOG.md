# Week 9 — Query Router (COMPLETE) → Retrieval Gate (NEXT)

## What was built: the query router

A three-tier router that classifies each question's TYPE and dispatches it.
Frozen at **96.2%** on its real scope (132 questions after eval re-scoping),
validated on a fresh adversarial stress set with zero hybrid leakage.

Routes: NUMERIC | CONCEPTUAL | HYBRID | REJECT
- Tier 1 (rules): unambiguous single-signal questions decide instantly, no LLM.
- Tier 2 (rules): ambiguous / both-signal questions escalate.
- Tier 3 (LLM): structured classification; HYBRID split into numeric + prose sub-queries.
  Cached by question hash (swap the in-memory cache for Redis/GPTCache later).

Files: router/signals.py (routing signals), router/router.py (tier logic),
router/test_router.py (grader), router/stress_generate.py + stress_run.py
(adversarial stress harness).

## Key architectural decisions (the throughline)

1. **Router classifies TYPE; the gate resolves COMPANY.** The router is fully
   company-agnostic. It never resolves which company a question is about, never
   checks corpus membership, never handles typos. All company logic moved to
   gate/company_resolution.py.

2. **REJECT is a positive assertion — only made when certain.** The router
   rejects ONLY company-independent cases: impossible/malformed year (1920, 3000,
   "year zero") and unsupported numeric concept asked as a number (free cash
   flow, gross margin). Uncertainty escalates to the LLM; it never rejects.

3. **Attack STRUCTURE, not vocabulary.** Hybrid detection uses the "second
   clause" signature ("...and what reasons did each give") rather than counting
   companies or chasing phrasings. Structure is bounded/stable; vocabulary is an
   endless treadmill. Explanatory vocab (why/drivers/reasons/narrative) was added
   as a *bounded* causal-language set, not open-ended phrase-chasing.

4. **Escalate on ambiguity; let the LLM catch the long tail.** Rules handle the
   confident common cases cheaply; anything unclear defers to the LLM. Rules are
   measured by how few cases they wrongly force-decide, not by coverage.

## Verified properties
- NUMERIC recall 100%, HYBRID recall 100%, zero HYBRID leakage (the critical
  failure mode — a hybrid answered as a single route — does not occur).
- **Validated on a FRESH adversarial stress set** (stress_set_v2, never tuned
  against): zero hybrid leakage held on unseen data — the structural
  second-clause escalation generalized rather than overfitting.
- Adversarial stress test surfaced + fixed: boundary "prose-about-a-number"
  (explanatory/causal vocab incl. drove/contributors/drivers/reasons/narrative),
  hybrid structural leaks (second-clause escalation), ticker-symbol recognition,
  malformed years.

## Known deferred items (for the gate phase)
- **"JP Morgan Chse" typo resolves as JPM** instead of flagging — the corpus
  substring "jp morgan" matches before the typo check runs. Gate resolution
  needs exact-match-vs-near-miss ordering fixed. (This is the 1/22 the gate
  currently misses.)
- **~3 both-signal prose stragglers** ("factors contributed to the increase in
  revenue") escalate correctly but offline guess REJECT/HYBRID; the LLM tier
  resolves them. Noise floor — do not tune the rules further.
- **A few verbose-phrasing LLM-judgment calls** — on adversarially clause-heavy
  questions the LLM tier occasionally over-escalates (safe WASTE leak) or
  misjudges. Noise floor, LLM's call, not a rule bug.

## Eval re-scoping (done this session)
decline_eval.json (50) split by owner:
- decline_router.json (6): year/concept rejects the ROUTER owns.
- decline_gate.json (44): company-based rejects the GATE owns — this is the
  ready-made eval for the next phase.
test_router.py now uses decline_router.json.

## NEXT PHASE: the retrieval gate
Seed already written and tested: gate/company_resolution.py with resolve()
returning the five-case outcome (resolved / out_of_corpus / typo / use_context /
need_company). Catches 21/22 of decline_gate.json (the JP-Morgan-Chse case is
the known gap).

To build:
1. Fix exact-vs-near-miss ordering in resolve() (the JP Morgan Chse case).
2. Wire resolve() as retrieval's front door: reject/clarify before spending
   embedding + generation (the cost/latency/hallucination guard).
3. Numeric path: SQL against facts.sqlite behind resolved tickers.
4. Prose path: small-to-big against Pinecone.
5. Grade company resolution against decline_gate.json (target ~100%).
6. Typo "did you mean?" + "which company?" confirmation live in the conversation
   layer ABOVE the gate (interactive; the gate provides detection primitives).