# FilingsIQ — Production RAG over SEC Filings

A retrieval system that answers natural-language questions about public companies' SEC filings — engineered so it **never guesses at a number**. Financial facts are served from structured XBRL data with exact-match guarantees; narrative questions (risk factors, strategy, MD&A) are served from a hybrid vector-search pipeline with reranking. A query router decides which path each question needs.

Built solo, ground-up: ingestion, retrieval, security, and serving — not a notebook demo.

---

## Why the design looks like this

A plain RAG pipeline over financial filings has one fatal flaw: **it retrieves numbers as fuzzy text.** Ask for "net income in 2024" and dense embeddings will happily surface 2025's figure, or a similarly-worded line from the cash-flow statement, because *phrasing* similarity outranks *factual* correctness. For a finance tool, a confidently-wrong number is worse than no answer.

FilingsIQ splits the problem in two and routes between them:

| Path | Source | Retrieval | Guarantee |
|------|--------|-----------|-----------|
| **Numbers** | SEC XBRL company-facts API | Exact structured lookup (SQL) | The filed, GAAP-tagged figure — provenance-tracked, verified against public data |
| **Prose** | Filing narrative (Docling) | Hybrid dense + BM25 + RRF → rerank → small-to-big | Grounded in retrieved filing text |

The two paths are kept **deliberately separate** — numbers are never embedded as fuzzy text, and prose is never pre-attached to numeric answers by embedding similarity. The router combines them only at answer time. That separation *is* the product: it's what lets the system promise an exact number instead of a plausible one.

---

## Corpus & scale

- **20 companies** across Tech, Banking, Pharma, and Industrials
- **40 filings** ingested and validated (10-K + 10-Q); **10-K prose** embedded this phase
- **6,779 prose chunks** in Pinecone; **2,503 parent sections** in SQLite for small-to-big retrieval
- **300 structured facts** (20 companies × revenue/net-income/total-assets × 5 years) in SQLite, provenance-tracked to the exact XBRL tag
- Full-corpus embedding cost: **~$0.14**

---

## Key engineering results

- **Exact-number guarantee, validated end-to-end.** All 20 companies resolve revenue / net income / total assets to current-period values, cross-checked against public figures (100% revenue match) — including a bank (JPMorgan, $4.42T assets) whose XBRL tagging differs fundamentally from a hardware company's.
- **Hybrid retrieval + reranking beats dense-only on precision.** RRF fusion of dense + BM25, then a Cohere cross-encoder rerank, surfaced correct financial line items that were entirely absent from the dense-only top-3.
- **Security tested, not assumed.** 14/14 adversarial prompt-injection attacks (OWASP LLM01–LLM07) defended by a 4-layer guardrail architecture. See [DEVLOG](DEVLOG.md).
- **Validation caught silent data corruption at every stage** — stale XBRL tags, wrong CIKs, quarterly-period leakage, table-column triplication — that would otherwise have poisoned retrieval invisibly.

---

## The bug worth reading (why validation is a first-class citizen here)

Mid-ingestion, an XBRL cross-check reported `total_assets` present in only **2 of 20** companies — an alarming near-total extraction failure. It would have been easy to "fix" the extraction pipeline in response.

The extraction was fine. The **validator** was broken, in three independent ways: it searched a truncated diagnostic file that only saved the first 8 rows of each table (total assets sits below row 8 on a balance sheet), it matched case-sensitively (`total assets` vs. `Total assets`), and it anchored to the wrong fiscal period. Re-running against the *full* extracted text recovered every figure — the data had been present the whole time.

The lesson, which now governs the whole project: **a validator is real code with real bugs, and it lies in both directions — false alarms and false confidence.** Every "failure" in the ingestion phase turned out to be a check bug, not a pipeline bug. The discipline that came out of it — point validation at the full real output, and sanity-check the validator against a known-good baseline before trusting its verdict — is why the exact-number guarantee is trustworthy rather than just claimed.

---

## Architecture

```
                          ┌─────────────────┐
   User question  ───────▶│  Query Router   │  classify → numbers / prose / both / reject
                          └───┬─────────┬───┘
                              │         │
                  ┌───────────▼──┐   ┌──▼──────────────────────────┐
                  │ NUMERIC PATH │   │  PROSE PATH                  │
                  │ XBRL facts   │   │  hybrid (dense + BM25 + RRF) │
                  │ SQL lookup   │   │  → Cohere rerank             │
                  │ (exact)      │   │  → small-to-big expand       │
                  └───────┬──────┘   └──────────────┬──────────────┘
                          │                          │
                          └──────────┬───────────────┘
                                     ▼
                        ┌──────────────────────────┐
                        │  Guardrailed generation   │  grounded, structured output
                        └──────────────────────────┘
```

**Ingestion (offline):** EDGAR fetch → Docling prose extraction + XBRL fact extraction → dedup → validate → structure-agnostic chunking → validate → embed → upsert. Numbers and prose stay separate chunk types; tables are dropped from the embedded corpus because their values live in the exact numeric store.

---

## Stack

**Retrieval & LLM:** LangChain · LangGraph · OpenAI (gpt-4o-mini, text-embedding-3-small) · Pinecone serverless · FAISS (local dev) · Cohere rerank-english-v3.0 · BM25 (rank_bm25)

**Data:** Docling (prose) · SEC XBRL company-facts API · SQLite (facts + parent store) · tiktoken

**Serving & security:** FastAPI + uvicorn (SSE streaming) · JWT (PyJWT) + RBAC · AES-256-GCM · 4-layer prompt-injection guardrails

**Reliability & eval:** Redis (exact + semantic caching) · tenacity · RAGAS · LangSmith · Pydantic structured outputs

---

## Repository layout

```
week8/
├── config.py                 shared config (models, index, paths)
├── lookup_filings.py         EDGAR CIK + filing discovery (KNOWN_GOOD_CIKS override)
├── save_filing_list.py       persist target filing list
├── extract_all.py            Docling prose extraction + full-text cache
├── dedup_columns.py          per-table column-triplication fix
├── section_splitter.py       SEC Item boundary detection
├── chunker.py                structure-agnostic chunking (tables kept atomic)
├── chunk_loader.py           chunk assembly + metadata
├── save_chunks.py            persist chunks
├── build_parents.py          small-to-big parent store
├── embed_and_upsert.py       batch embed → Pinecone (idempotent, deterministic IDs)
├── xbrl_companyfacts.py      XBRL fact extraction (numeric path)
├── load_facts.py             load facts → SQLite (provenance-tracked)
├── validate*.py              validation gates (extraction / chunker / corpus)
├── prose_health.py           prose loss + duplication check
├── ingestion_design.md       ingestion design notes
├── scratch/                  exploratory + diagnostic scripts (not the live path)
└── SESSION_LOG.md            Week 8+ engineering log

DEVLOG.md                     Weeks 3–7 build journal (RAG fundamentals → serving + security)
```

Regenerable data (raw filings, caches, SQLite DBs) is gitignored — the repo holds the code that produces the corpus, not the corpus itself. Clone, set `.env`, run the pipeline, rebuild.

---

## Setup

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Create `.env` at the project root:

```
OPENAI_API_KEY=
PINECONE_API_KEY=
COHERE_API_KEY=
TAVILY_API_KEY=
LANGCHAIN_API_KEY=
LANGCHAIN_TRACING_V2=true
LANGCHAIN_PROJECT=rag-agent
JWT_SECRET_KEY=
```

---

## Documentation

- **[SESSION_LOG.md](week8/SESSION_LOG.md)** — Week 8+ engineering log: ingestion, extraction validation, the XBRL numeric path, chunking, and embedding, with the bugs and design decisions behind each.
- **[DEVLOG.md](DEVLOG.md)** — Weeks 3–7: RAG fundamentals, CRAG/Self-RAG evaluation, security + reliability, scale + advanced retrieval, and the FastAPI serving layer with the full guardrail architecture.

---

## Status

Ingestion and embedding complete: a clean, validated, dual-path corpus (exact numeric store + embedded prose) over 20 companies. Next: a corpus-specific eval set, then the query router (numbers / prose / both / honest decline), then retrieval assembly with reranking and small-to-big.

*Self-directed AI engineering project. Single author.*

---

### Documented limitations (carried forward honestly)

- **Sector coverage:** Tech, Banking, Pharma, Industrials only. Insurance, Utilities, and REITs use meaningfully different XBRL tagging (e.g. "premiums earned" vs. "revenue") and are not validated.
- **~20% of filings** have no cleanly detectable Item headers, so those chunks carry no `section_item` label. Content is complete and searchable; only section-filtered retrieval is affected.
- **Numeric scope is deliberate:** 3 concepts × 5 years. Out-of-scope numeric queries decline honestly rather than guess — correctness over coverage.