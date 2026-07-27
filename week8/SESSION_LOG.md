# SESSION_LOG — Week 8+

Engineering log for the ingestion and embedding phases of FilingsIQ. Weeks 3–7 (RAG fundamentals through the FastAPI serving layer) are in [../DEVLOG.md](../DEVLOG.md).

The recurring theme of this phase: **expect validators to be buggier than the thing they validate.** Nearly every "failure" here turned out to be a check bug, not a pipeline bug.

---

## Extraction validation — Docling table triplication

**Goal:** Determine whether Docling can reliably extract financial statement tables from SEC HTML filings, or whether XBRL needs to be a separate required extraction path.

### Method
Ran Docling against 8 filings across 4 companies chosen for structural diversity (not just industry): Apple (tech, self-filed clean HTML), JPMorgan (bank, different statement shape/filing agent), Microsoft (tech, different filing agent than Apple), ExxonMobil (energy/industrial, different statement shape again). One 10-K and one 10-Q per company.

For each, extracted all `doc.tables`, classified which were balance sheet / income statement / cash flow by keyword match, and checked (a) whether the numbers matched known-correct figures, and (b) whether adjacent columns were identical (a "triplication" artifact suspected from an earlier Apple-only pass).

### Result
| Filing | Numbers correct? | Columns triplicated? |
|---|---|---|
| Apple 10-K | Yes | Yes |
| Apple 10-Q | Yes | Yes |
| JPMorgan 10-K | Yes | Yes |
| JPMorgan 10-Q | Yes | Yes |
| Microsoft 10-K | Yes | **No** |
| Microsoft 10-Q | Yes | **No** |
| ExxonMobil 10-K | Yes | Yes |
| ExxonMobil 10-Q | Yes | **No** |

**Every filing's underlying numbers were correct and complete** — no data loss. Total net sales, net income, balance sheet line items, cash flow items all matched known-correct figures (cross-checked against companyfacts API and public earnings releases).

**However:** 6 of 8 filings showed a structural artifact where Docling splits merged/spanned HTML cells (likely `colspan` in source) into multiple identical DataFrame columns instead of one logical column. NOT predictable by company alone (Microsoft never showed it) NOR by form type alone (ExxonMobil's 10-K showed it, its 10-Q did not).

### Conclusion
- No separate XBRL path is required *for accuracy* — Docling's underlying extraction is correct. (The dual-path design was later kept for other reasons — exactness guarantee, provenance, cross-company comparability — see the XBRL Numeric Path entry.)
- A column-deduplication step IS required, applied conditionally per-table (not per-company or per-form-type), since the artifact is inconsistent even within a single filer.
- Detection validated: check whether adjacent columns are identical; if so, collapse to one. Correctly flagged all 6 affected filings, left Microsoft's clean tables untouched.

---

## Programmatic CIK + filing lookup

Replaced manual web-search verification with `lookup_filings.py`, using two SEC APIs directly:
- `company_tickers.json` for ticker→CIK mapping
- `submissions/CIK##########.json` for latest 10-K/10-Q per CIK

**Bug found and fixed:** SEC's ticker map returned an incorrect CIK for XOM (2115436, not a real ExxonMobil CIK) — caught because we'd already manually verified XOM's real CIK (34088) earlier. Added a `KNOWN_GOOD_CIKS` override dict so manually-verified CIKs always beat the (occasionally unreliable) ticker map. General pattern: don't trust bulk reference data blindly when you have independently verified ground truth for specific entries.

**Result:** all 40 filings (20 companies × 10-K + 10-Q) resolved. Saved to `data/filing_list.json` via `save_filing_list.py`.

---

## Extraction validation arc + the validator-bug lesson

### What we set out to do
After extracting all 40 filings with Docling + dedup, validate that extraction didn't lose financial data before chunking.

### Validation approaches tried
1. **Structural checks (abandoned):** year-count per table, "largest table per category", empty-cell %. All fragile — false positives on legitimate sub-fragments, and couldn't distinguish "table of contents matched as cash flow" (JPM) from real data. Structural heuristics don't generalize across filer formats; every new filing broke the last rule.
2. **XBRL cross-check (kept, but had to be fixed):** pull official anchor figures (revenue, net income, total assets, operating cash flow) from companyfacts API, confirm they appear in the ingested text. Industry-agnostic, tests data-loss directly, cheap, scalable.

### The big lesson: our VALIDATORS were buggier than the extraction
The XBRL cross-check reported `total_assets` present in only **2/20** companies — an alarming near-total failure suggesting broken extraction. It was FALSE. Root causes, all in the validator, not the pipeline:
- Searched the `reports/*.txt` files, which only saved `df.head(8)` of each table. "Total assets" sits below row 8 in a balance sheet — truncated out of the artifact we searched.
- Case-sensitivity: searched lowercase "total assets" vs. actual "Total assets".
- Wrong-period anchoring: XBRL "newest" value is often a quarterly figure whose exact number isn't printed in the specific filings ingested.

**Proof:** re-extracted Apple's 10-K to FULL markdown (no truncation) and grepped. `Total assets` FOUND, `364,980` FOUND, `359,241` FOUND. The data was present the entire time. Extraction was never broken.

### Takeaway
A validator that searches an incomplete copy of the data reports false data-loss. We nearly "fixed" extraction that was working fine. Validation code is real code with real bugs — a validator you haven't debugged lies in both directions (false alarms AND false confidence).

---

## Ingestion + extraction validation: COMPLETE

Extraction (Docling + column-dedup) validated across all 20 companies / 40 filings on four independent dimensions. All pass.

### 1. Numbers present (XBRL cross-check)
Anchor figures confirmed in full extracted text: net_income 20/20, total_assets 20/20, op_cash_flow 19/20, revenue 16/20. The misses are validator-side (concept-alias gaps / scale-period edges for XOM, NVDA, BA, T revenue; JPM cash flow), not data loss — confirmed by prose + manual checks.

### 2. Structure present
Full char counts sensible (Apple 480K, JPM 4.7M, BAC 7.2M), thousands of table rows per filing, all key narrative sections detectable. Note: Docling emits NO markdown `#` headers — section titles are plain-text `Item N.` lines (matters for chunking).

### 3. Prose present, not lost
`prose_health.py` measured narrative word volume per filing. Every 10-K at or above the Apple baseline (24,345 words); range ~35K–133K. Critically, XOM and WMT — which LOST section headers in extraction — still have full prose volume (36K, 40K words): missing headers ≠ missing content.

### 4. Prose not duplicated
Sentence uniqueness ratio 0.83–0.99 across all filings (0.85+ = mostly distinct). Table column-triplication did NOT bleed into prose. Lowest were META (0.83) and KO (0.86) — normal boilerplate, well above the 0.60 concern threshold.

### Key cross-cutting lesson
Our validators were repeatedly buggier than the extraction they checked. The scariest scare (total_assets 2/20) was entirely a truncated-diagnostic artifact. Every "failure" this phase was a check bug (truncation, case-sensitivity, wrong-period anchoring, fragile section-finding, over-strict thresholds), not a pipeline bug. Fix: always point validation at the FULL real output, and sanity-check the validator against a known-good baseline (Apple, manually confirmed) before trusting its verdict.

### Consequences for chunking
- Chunk from the full markdown per filing (`data/processed/<T>/<T>_<form>_full.md`).
- Do NOT chunk on section headers — inconsistent across filers (present-plain for most, merged for JPM/BAC, absent-from-body for XOM/AMZN/WMT). Header-dependent chunking would break on 3+ filers.
- Use universal structure-agnostic chunking (size + paragraph/table-aware boundaries). Attach section labels as OPTIONAL metadata only where a header is cleanly detectable. Never lose content to a missing boundary.
- Rely on semantic retrieval to surface the right chunk regardless of labeling; eval/RAGAS is the downstream correctness net.

---

## Chunking — COMPLETE

### Design
Structure-**agnostic** chunking (size + paragraph/table-aware boundaries) → tables kept atomic. Section labels attached as OPTIONAL metadata only where a header is cleanly detectable — never used as split boundaries, because headers are inconsistent across filers (~20% have none). This supersedes the earlier "section-aware split" plan, which the multi-filer validation ruled out.

Config: 800 tokens, 100 overlap, 1200-token table ceiling, tiktoken `cl100k_base`, sized against text-embedding-3-small (8191 limit).

### Library vs custom audit
- LangChain `RecursiveCharacterTextSplitter` — prose within a chunk-size budget. No reason to rewrite it.
- Custom — table atomicity. Splitters break tables mid-row; Week 6 proved this destroys retrieval on financial questions (net income table split across 3 chunks at size=800).

### Validation (all 40 filings)
- Content loss: 0 missing lines
- Coherence: 0 issues (no mid-word prose starts, no headerless table fragments)
- Over embedding limit: 0
- Metadata keys present: all filings
- **Total: 13,939 chunks** (prose + tables, all 40 filings; tables and 10-Q are dropped later at the embedding stage)

### Accepted limitation
~20% of filings (7–8 of 40) have no detectable Item headers → no `section_item` label. Per-filing, not per-company — depends on how Docling rendered that specific document. Impact limited to section-filtered retrieval; semantic search and small-to-big unaffected. Documented, not fixed.

### Principle carried forward
Validate at each stage against real data. Don't generalize from one company. Expect validators to be buggier than the thing they validate.

---

## XBRL Numeric Path — COMPLETE

### Architecture confirmed
XBRL owns numbers, Docling owns prose, tables discarded from embedding. Numbers come from the SEC companyfacts API, verified — never Docling tables. (Note: this is not because Docling's numbers were wrong — the triplication study proved them accurate. It's for the exactness guarantee, provenance, and cross-company comparability that a structured store gives and fuzzy retrieval cannot.)

### Facts store: `data/facts.sqlite`
20 companies × 3 concepts (revenue, net_income, total_assets) × 5 years = 300 rows. Schema: `ticker, concept, value, unit, period_end, fiscal_year, form, source_tag, entity_name`. PK `(ticker, concept, period_end)`.

### Bugs found and fixed
- **XOM:** SEC ticker map points to ExxonMobil Holdings (a fee shell); override to CIK 34088.
- **BAC:** companyfacts `entityName` says "BofA Finance LLC" but CIK 70858 IS the parent (891 tags, $3.4T assets) — name quirk, data correct, no fix.
- **Revenue:** preferred-tag-first returned stale retired tags (BA 2019, NVDA 2022). Fix: pool ALL preferred tags, `max(end)` picks the current one. `Revenues`-first for total.
- **Quarterly leak:** companyfacts tags quarters with `form=10-K` and mislabels some 90-day periods as `fp=FY`. Fix: require BOTH `fp==FY` AND period span > 350 days.
- **Provenance:** every fact stores `source_tag` — the tag IS the definition.

### Validated
All 20 revenues cross-checked against public figures (100% match). Ranking, trend, and YoY-comparison queries all correct.

### Known limits (deliberate)
- 3 concepts only. Out-of-scope queries decline honestly (correctness > coverage).
- Cross-company revenue approximate (bank vs. retailer not truly comparable); `source_tag` makes the definition auditable.
- Pre-2017 Apple revenue uses a different tag (`Revenues` vs. `RevenueFromContract`) — visible in provenance; irrelevant at the 5-year cap.

---

## Embedding Phase — COMPLETE

### Corpus
Prose-only: **6,779 chunks** embedded (down from the 13,939 total after dropping tables and 10-Q filings). Model text-embedding-3-small, dotproduct metric, namespace v1. Tables dropped (numbers live in XBRL/SQL). 90% section-labelled.

### Small-to-big
2,503 parents in `data/parents.sqlite`, 3 children each, avg ~1,052 tokens. Every child's metadata carries `parent_id`; integrity validated.

### Validation gate (all pass)
vector count 6779/6779, parent_id integrity, metadata complete, smoke query ok.

### Observation for eval
Smoke query "supply chain risks": 20 children → 17 unique parents (low clustering). Revisit parent size (`CHILDREN_PER_PARENT`) once an eval set exists; current 3 gives ~1,052-token parents, which may be small. **Do NOT tune blind** — build a corpus-appropriate eval set first (the Week 4 set is Apple-only and stale). Could be genuine query diffuseness (20 companies each discuss supply chain once) or parents running small; can't distinguish without an eval set.

---

## Session: repo hygiene + docs restructure

### Repo cleanup
Root had ~90 mixed files (pipeline + one-off diagnostics). Sorted into 16 pipeline files at root + `scratch/` for exploratory/debug scripts. Nothing deleted — `scratch/` is kept as an audit trail.

Gitignore audit: confirmed `.env` never committed (`git ls-files` clean), `data/` and `.cache/` already ignored, added `reports/` (stale Jul-18 table dumps, regenerable). Committed the deletions of the old committed data corpus so it leaves the remote.

Principle locked in: the repo holds the code that produces the corpus, not the corpus. Raw filings, caches, and the sqlite stores are all regenerable and gitignored. Clone + `.env` + run rebuilds everything.

### Auth timing decision (not a gap — a sequencing call)
JWT/RBAC (built Week 5, wired to a FastAPI skeleton Week 7) is NOT wired to the ingestion pipeline, and shouldn't be. Auth guards a user-facing endpoint; ingestion is a batch script with no door to lock. RBAC wires onto the `/ask` query endpoint when it's built (retrieval phase), as a one-line dependency using the existing `check_access()`.

### Docs restructure
Split the monolithic README into three docs:
- `README.md` — front door (impact, architecture, setup, links out)
- `DEVLOG.md` — Weeks 3–7 build journal (moved out of README)
- `SESSION_LOG.md` — this file, Week 8+

Corrected a stale rationale carried from Week 7: the dual-path design (XBRL owns numbers, Docling owns prose) is kept for exactness, provenance, and cross-company comparability — NOT because "Docling can't extract numbers." Multi-company validation this phase showed Docling's underlying numbers were accurate; the empty-cell rendering was a display artifact. Conclusion unchanged, reasoning corrected.

---

## Next (retrieval phase — not started)
1. **Eval set** for the 20-company corpus — prerequisite for tuning anything (including the parent-size question above). The Week 4 set is Apple-only and stale.
2. **Query router** — numbers (SQL) vs. prose (vector) vs. both, with a synonym map and honest declines.
3. **Retrieval assembly** — small-to-big fetch, optional rerank, history-aware query rewriting for follow-ups.
4. **Query endpoint** — where auth/RBAC finally wires in.