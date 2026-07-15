# Week 8 — Session Log

**Goal:** Ingestion pipeline for 20 companies (10-K only) + auth/RBAC.

---

# Day 1 — Extraction Foundations

## Goal for the day
Validate two separate extraction paths needed for multi-company ingestion: structured financial facts (XBRL) and narrative filing text (Docling) — before scaling either one across all 20 target companies.

## 1. XBRL Fact Extraction — `week8/xbrl_companyfacts.py`

**Approach:** Instead of parsing raw XBRL instance documents and manually resolving `contextRef` → period mappings, this uses SEC's `companyfacts` API (`data.sec.gov/api/xbrl/companyfacts/CIK##########.json`), which returns every tagged fact a company has filed, pre-resolved to actual periods, forms, and units.

**Design:**
- **Preferred-tag lookup first** — a small list of known-correct `us-gaap` tags per financial concept (`RevenueFromContractWithCustomerExcludingAssessedTax`, `NetIncomeLoss`, `Assets`), checked directly with no ambiguity.
- **Fuzzy label-match fallback** — for tags not in the preferred list, searches across *all* taxonomies (not just `us-gaap`) by matching keywords against tag labels, falling back to the tag name itself if no label exists. All matches are pooled rather than picked by a single heuristic.
- Values are never assumed to be USD or 10-K only — every fact carries its actual `unit` field, and annual lookups accept `10-K`, `20-F`, and `40-F`, so non-USD or foreign-filer data isn't silently dropped.

**Hard bug found and fixed:** An early version picked between multiple matching tags by choosing whichever had the most historical data points. This picked the wrong tag twice:
- For revenue, it selected `SalesRevenueNet` — a tag Apple stopped using after the 2018 ASC 606 accounting standard change — over the tag Apple currently files under, simply because the old tag had more years of accumulated history.
- For total assets, it selected `IncreaseDecreaseInOtherOperatingAssets` — a cash-flow statement line item — because "assets" appeared in its label and it had more filed data points than the real `Assets` tag.

Fixed by preferring exact known-good tags first, and only pooling fuzzy matches when no preferred tag exists.

**Validation:** Tested against Apple (hardware/tech) and JPMorgan Chase (banking). All six values cross-checked against independent public financial data and matched exactly:

| Company | Revenue | Net Income | Total Assets |
|---|---|---|---|
| Apple (FY2025) | $416.16B | $112.01B | $359.24B |
| JPMorgan Chase (FY2025) | $182.45B | $57.05B | $4.42T |

JPMorgan resolved via the preferred-tag path with zero fallback needed — the standard revenue tag held up even for a fundamentally different business model (interest + fee income vs. product sales).

## 2. Docling Prose Extraction

**Hard bug found and fixed (file discovery):** SEC's EDGAR filing index page uses root-relative links (`/Archives/edgar/...`) for both actual filing documents *and* general site navigation (privacy policy, careers, etc.) — no structural difference at the link level. An initial filter assumed root-relative links were site nav and skipped them all, causing the fetcher to fall through to unrelated pages (at one point resolving to SEC's `/privacy.htm`). Fixed by scoping candidate links to the filing's own directory path and excluding known non-content patterns (`R##.htm` XBRL viewer fragments, exhibits, index pages).

**Result:** Once pointed at the correct file (`aapl-20250927.htm`), Docling successfully extracted clean prose from Apple's full FY2025 10-K (480K+ characters), with headings preserved.

**Confirmed limitation (matches Week 7 finding):** Financial statement tables rendered as markdown tables with correct row/column structure but entirely empty cells — a direct result of iXBRL tagging, where visible numbers are wrapped in inline XBRL tags rather than plain table-cell text. Reproduced against the live document, confirming the decision to route all numerical data through the XBRL companyfacts path.

**Section isolation:** Regex-based boundary matching on Docling markdown output:

| Section | Length |
|---|---|
| Item 1A – Risk Factors | 68,168 chars |
| Item 7 – MD&A | 28,061 chars |

## Design decisions locked in (Day 1)
- **XBRL owns numbers.** All financial facts extracted via SEC's companyfacts API, never via Docling table parsing.
- **Docling owns prose.** Risk Factors, MD&A, and other narrative sections via Docling, with tables in those documents ignored since XBRL supersedes them.
- These become **separate chunk types** at ingestion — not merged into one linear document — so numerical queries can route directly to structured facts rather than depending on retrieval to find the right prose chunk.

---

# Day 2 — Scaling + Section Extraction

## Completed today

### 1. XBRL: fixed preferred-tag pooling bug, validated 20/20
- **Bug:** `get_concept_values` returned after checking only the *first* preferred tag that had any data, due to an indentation error placing the pooled-results check inside the tag loop rather than after it.
- **Impact:** Boeing's revenue resolved to a stale **2019** value ($76.6B) instead of its FY2025 figure ($89.5B) — Boeing stopped using `RevenueFromContractWithCustomerExcludingAssessedTax` after 2019 and switched to plain `Revenues`, but the loop never reached the second tag.
- **Fix:** pool values across *all* preferred tags, then let recency selection pick the current one. Same failure class as the Apple/`SalesRevenueNet` bug from Day 1, now fixed generically rather than per-company.
- **Also fixed:** Ford CIK typo (`0000037990` → `0000037996`).
- **Result:** all 20 companies resolve revenue / net income / total assets to current-period values. Goldman Sachs required the fuzzy fallback path — resolved, but the matched tag hasn't been manually reviewed.

**Extended validation — 7 companies, 5 industries, all correct post-fix:**

| Company | Industry | Revenue | Net Income | Total Assets |
|---|---|---|---|---|
| Apple | Tech | $416.16B | $112.01B | $359.24B |
| Microsoft | Tech | $281.72B | $101.83B | $619.00B |
| Tesla | Tech/Auto | $94.83B | $3.79B | $137.81B |
| JPMorgan Chase | Banking | $182.45B | $57.05B | $4.42T |
| Bank of America | Banking | $113.10B | $30.51B | $3.41T |
| Johnson & Johnson | Pharma | $94.19B | $26.80B | $199.21B |
| Boeing | Industrials | $89.46B | $2.24B | $168.24B |

### 2. Docling: fixed EDGAR file discovery (CIK padding)
- **Bug:** `get_filing_index` applied `cik.zfill(10)` when building the Archives URL. The `companyfacts` JSON API requires the zero-padded 10-digit CIK, but EDGAR's `/Archives/edgar/data/` path uses the **unpadded** CIK. Every filing fetch silently resolved to a wrong-but-valid page, so href scoping never matched and all 20 companies failed with "No main filing doc found."
- **Fix:** `str(int(cik))` for the Archives path; keep zero-padding only for the JSON API.
- **Result:** all 20 companies now fetch and convert successfully.

### 3. Docling: markdown normalization
- SEC filings use HTML tables for layout, not just tabular data. Docling faithfully converts that structure, producing repeated cell content and pipe clutter around headings (e.g. Amazon: `| Item 1A. | Item 1A. | Item 1A. | Risk Factors | Risk Factors | Risk Factors |`).
- Added `normalize_table_noise()`: strips pipes, collapses whitespace, and collapses immediately-repeated phrases before any heading detection runs.
- **Result:** fixed Amazon and General Electric outright (0 sections → 22 each), with no regression on companies already working.

### 4. Section extraction: sequential ordered walk
Final working approach for standard filers:
1. Normalize markdown (above)
2. Walk items in canonical order (`1`, `1A`, `1B`, `1C`, `2` … `16`)
3. For each item, find the first occurrence of its title keyword that is a real heading — rejecting TOC entries and cross-references
4. Each section's **end** = the next *found* item's start (absent items are skipped, not treated as errors)

**Status: 18 of 20 companies extract cleanly**, with sensible per-section lengths (e.g. Apple — Item 1A: 84,791 chars; Item 1B "None.": 226 chars; Item 7: 18,926 chars).

## Two companies not resolved — root causes fully diagnosed

### Morgan Stanley — bare headings with no structural markers
- Body headings carry **no item number**: the real Item 1A heading is literally just `Risk Factors`, immediately followed by body text **on the same line** with no break. (Confirmed against the live SEC filing — MS's *2007* filing used `Item 1A. Risk Factors.`; the FY2025 filing does not. The convention changed.)
- Consequence: both discriminating signals are unavailable —
  - `has_exact_item_number` → never fires (no number)
  - `looks_like_heading_line` → never fires (heading not isolated on its own line)
- **Item 1A start detection is correct** (pos 80,670, manually verified against the real filing). The failure is that *intermediate* sections (1C, 2, 3, 4, 5, 6, 7, 7A) are never found, so Item 1A has nothing to cap it and absorbs ~900K chars up to the next item it can find (1B at 980,207).
- **Scoring model was built and tested** (weighted signals: exact item +5, markdown heading +4, TOC anchor −4, bare heading shape +2, negative context −3, length support +1). It ranks correctly — real candidates score positive, cross-references score −2.0 — but every real candidate tops out at +1.0 because the only signal that fires is length support. It cannot distinguish the real heading from other +1.0 prose mentions.

### Citigroup — Items are NOT contiguous spans
This is the more fundamental finding.
- Citi's TOC lists **multiple non-contiguous page groups per item**:
  - `Cybersecurity 55-57, 113-115`
  - `Business 4-36, 121-127, 129, 160-164, 299-300`
- Citigroup does not organize its 10-K into linear, one-block-per-item sections. A single Item's content is **scattered across several disconnected parts of the document**.
- **This breaks our data model, not just our detection.** The entire approach assumes `section = (start, end)` — one contiguous span. For Citigroup that is structurally false: Item 1C cannot be represented as one span because it exists in at least two separate places.
- Secondary confirmed issues:
  - Items with no content (e.g. 1B "Unresolved Staff Comments — Not Applicable") appear **only in the TOC**, with no body heading. This is legitimate; absent items are now skipped rather than erroring.
  - Single-word keywords collide with prose: `cybersecurity` matched *inside* an Item 1A risk-factor title ("…Susceptible to an Increasing Risk of Evolving, Sophisticated **Cybersecurity** Incidents That Could Result in theft, Loss…"), cutting Item 1A mid-sentence and starting a fake Item 1C at 231,054.
- **Fix applied and working:** extended TOC detection to catch page-number-style TOC entries (`Risk Factors 49-62`), which Citi uses instead of anchor links. This correctly stopped the walk from anchoring sections to TOC lines.

---

## Design decisions (cumulative)
- **XBRL owns numbers, Docling owns prose.** Confirmed again on live data — iXBRL renders tables as empty-cell markdown.
- **Prose and facts stay in separate chunk types**, not merged into one linear document.
- **10-K only this week.** Most-recent 10-Q per company deferred to Week 9, alongside query routing (which needs to distinguish annual vs. quarterly anyway).
- **Do not pre-attach XBRL facts to prose chunks via semantic similarity.** Keep the two retrieval paths separate (structured lookup for numbers, vector search for prose) and let the query router combine them at answer time. Pre-attaching by embedding similarity would reintroduce fuzziness into the exact-numbers guarantee that is the project's core differentiator.

---

## Next session (6 hr block)

**Decide first — Citigroup's multi-span problem is a design fork, not a bug:**
- **Option 1:** build multi-span