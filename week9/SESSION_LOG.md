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

## Week 9 — Retrieval Layer: Numeric Path (single-company) ✅ COMMITTED

### State: single-company numeric path DONE and validated
- `numeric_eval.json`: **PASS 50/60, FAIL 0**, BLOCKED 10 (multi-company, deferred)
- `cc_numeric.json`: PASS 2/6, FAIL 3 (new ops, see below), BLOCKED 1
- Meaningful score = PASS vs FAIL excluding BLOCKED → single-company path is clean.

### Files (week9/retrieval/)
- `numeric_retriever.py` — resolve()+route() → normalized query object → parameterized
  SQL against week8/data/facts.sqlite. Returns structured facts or honest `no_data`.
  Guards: route!=NUMERIC → not_numeric; unresolved company → blocked.
  NOTE: no explicit REJECT branch yet — REJECT currently collapses into `not_numeric`
  (mislabel, cosmetic; REJECT questions live in decline_eval, not numeric_eval, so no
  score impact). Add a REJECT branch that threads router `reason` when convenient.
- `numeric_compute.py` — runtime compute layer. Infers operation from ROW SHAPE:
  1co/1yr→point, 1co/Nyr→delta|trend, Nco/1yr→ranking. Refusal guard: Nco×Nyr
  (compound) → unsupported/ambiguous (refuse, don't guess).
- `grade_numeric.py` — runs retrieval+compute vs eval ground truth. Uses `subtype`
  ONLY to pick the comparison field; delta/argmax come from compute() (test stays honest).
  Partitions PASS / FAIL / BLOCKED.

### The handoff contract (verified against real route()/resolve())
- route()['numeric_part'] = {concept (canonical snake_case), years:[...], tickers:[]}
- resolve() supplies tickers. route owns TYPE+concept+years; gate owns COMPANY.
- build_query() composes both into the normalized object.

### Remaining numeric work (3 named piles)
1. **Multi-company resolution** (11 BLOCKED) — resolve() handles ONE company; ranking &
   cross-company name several. Also "ExxonMobil" (no space) misflagged as typo of
   "exxon mobil". Biggest remaining numeric piece. Overlaps Bucket 2.
2. **New compute ops** — `gap` (cross-company difference, e.g. AMZN−WMT net income) and
   `growth-compare`. Deterministic; build once multi-company resolution feeds them.
   cc_gap currently mis-handled as ranking.
3. **Routing edge** — cc_growth_* questions route `not_numeric` (never reach compute).
   Decide: signal tweak vs acceptable decline.

### Documented LIMITATIONS (deliberate scope, not bugs)
- Compute infers operation from shape. Valid for current eval by construction
  (yoy=2yr, trend=3+yr, rank=multi-co). Can't express compound ops or disambiguate
  trend-with-2-years. → move intent from shape-inference to explicit operation tag
  from route()/signals WHEN eval grows to include those.
- Compute refuses bad SHAPES but CANNOT detect misparsed intent: a word-framed question
  ("rank by yoy", "which grew fastest") that route() mis-extracts arrives as a
  clean-looking shape and computes silently-wrong. Defense belongs at PARSE time, not
  compute. Untestable until eval has word-framed questions.

### NEXT SESSION — pick up here
Immediate options, in order:
  A. Multi-company resolution (unblocks 11 numeric + enables gap/growth ops) — pile #1.
  B. Then prose retrieval (small-to-big + hybrid search + conditional rerank) — the big one.
  C. Then answer generation (grounded) + end-to-end eval (RAGAS faithfulness).
Eval expansion (hard / should-decline / word-framed / adversarial-prose) folds in
alongside B–C. Remember: a correctly-DECLINED eval question is a PASS, not a fail.
Prose is where hallucination risk concentrates — that's where faithfulness measurement matters most.

## Week 9 — Multi-company Resolution + Numeric Path COMPLETE (numeric_eval 60/60) ✅

### Milestone
- **numeric_eval.json: 60/60, 0 FAIL, 0 BLOCKED** — single + multi-company numeric
  path fully working (point / yoy / trend / ranking).
- cc_numeric.json: 3/6 (3 remain — see below), 0 BLOCKED.
- Gate harness: 22/22 on decline_gate.json, no regression through all fixes.

### Gate fixes this session (company_resolution.py) — all one root area
Root cause across all: `_company_phrases` captured non-company / polluted spans,
and the exact-vs-fuzzy skip was mis-tuned. Fixed in layers, each validated 22/22:
1. Stray capitalized word ("Among NVIDIA...") no longer false-typos → multi-company
   resolves. Typo candidate must be a genuine near-miss, scored per-phrase.
2. word-subset skip: recognizes name FRAGMENTS ("Bank" ⊂ "bank of america",
   "Procter"/"Gamble" ⊂ "procter & gamble") while still catching typos.
3. exact-vs-fuzzy ordering: "JP Morgan Chse" → typo (not silent resolve). This was
   the previously-deferred 1/22 gap — now FIXED.
4. strip leading question-words: "Did UnitedHealth" / "Did Johnson" spans polluted
   resolution → _strip_leading_stop peels Did/Among/Which/etc before matching.

resolve() now correctly handles: single co, multiple named co, multi-word & "&"
names, near-typo (suggest), outsider (reject). Deferred still: in-context pronoun
merging + bare short-ticker input (Bucket 2, documented).

### Remaining numeric work — 3 cc cases (next session)
1. **cc_gap_net_income_AMZN_WMT_2024** — wants a GAP (AMZN−WMT difference), compute
   does ranking (argmax). Same row shape as ranking (multi-co, 1yr) → distinguishable
   ONLY by intent. **This is the shape-inference limitation coming due**: building
   `gap` forces the explicit-intent-vs-shape decision we documented. Likely need an
   operation tag from route()/signals, not more shape guessing.
2. **cc_growth ×2** (MSFT/NVDA, KO/WMT) — route `not_numeric`, never reach compute.
   Router-layer edge: "growth comparison across companies over years" not classified
   NUMERIC. Decide: signal tweak vs acceptable decline.

### After the 3 cc cases → numeric path fully done. Then:
  - Prose retrieval (small-to-big + hybrid search + conditional rerank) — the big one.
  - Answer generation (grounded) + end-to-end eval (RAGAS faithfulness).
  - Eval expansion (hard / should-decline / word-framed / adversarial-prose).

  ## CORRECTION — much of the "productionization" scope ALREADY EXISTS (Weeks 3-7)

Per earlier sessions, these were BUILT in Weeks 3-7 (old architecture):
- FastAPI + uvicorn API layer
- JWT auth (PyJWT) + RBAC + AES-256-GCM key encryption
- Guardrails: week7/guardrails.py check_input()/check_output(),
  14/14 vs OWASP LLM Top 10 injection (test_injection.py, test_guardrails.py)
- Query routing + agentic query decomposition
- Cohere rerank-english-v3.0 + BM25 hybrid retrieval
- Redis + GPTCache caching, tenacity retries
- RAGAS 0.3.3 + LangSmith eval tooling

### The REAL remaining question (not "build from scratch"):
Weeks 3-7 were the OLD system — Apple-only, LangChain/LangGraph, WEB/KEYWORD/REJECT
routing, Tavily. Weeks 8-9 are a REBUILD — 20 companies, new router
(NUMERIC/CONCEPTUAL/HYBRID/REJECT 96.2%), gate, facts.sqlite, new numeric + prose
paths. So the task is RE-WIRING / porting the existing components onto the new
architecture, NOT building them fresh:
- Does week7 guardrails work with the new gate+router pipeline, or need adapting?
- Does the old query-decomposition fit the new numeric/prose split?
- Does FastAPI/auth wrap the new pipeline, or the old one?
- Does the old hybrid/rerank apply to the new prose retriever?

NEXT SESSION: inventory week3-7 components against the week8-9 rebuild. Decide per
component: reuse as-is / adapt / rebuild. This likely SHRINKS remaining work vs the
"remaining scope" list above — much is port, not build.

### This shifts the timeline FAVORABLY
If auth/FastAPI/guardrails/decomposition mostly port over, the gap to a complete,
deployable pipeline is smaller than the raw scope list implies. Resume-start trigger
(pipeline works end-to-end) may be closer than the 2-week estimate. Confirm by doing
the inventory first.