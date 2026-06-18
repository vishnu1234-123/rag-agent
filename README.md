# RAG Agent — FilingsIQ

Built as part of the AI Engineer Roadmap (FilingsIQ project).
Production RAG pipeline over SEC 10-K filings with hybrid retrieval,
reranking, query routing, and agentic decomposition.

## Week 3 — RAG Fundamentals

Baseline RAG pipeline over a web document with retriever comparison and keyword-based evaluation.

### Results
| Retriever  | Avg Keyword Hit Rate |
|------------|----------------------|
| Similarity | 0.88                 |
| MMR        | 0.88                 |

**Key findings:**
- Similarity and MMR tied at 0.88 on this document and question set
- ID 9 revealed a lexical overlap problem — API-Bank chunks ranked higher than the definition chunk due to keyword frequency
- MMR fixed ID 9 completely (0.00 → 1.00) by fetching diverse candidates
- Question wording directly affects retrieval quality
- Keyword eval undercounts real retrieval quality — RAGAS semantic evaluation added in Week 4

### What this covers
- Document loaders — WebBaseLoader, PyPDFLoader
- Text splitters — RecursiveCharacterTextSplitter, CharacterTextSplitter, TokenTextSplitter, SemanticChunker
- Embeddings — OpenAI text-embedding-3-small vs BGE-base-en-v1.5 (local)
- Vector stores — InMemoryVectorStore, FAISS (with persistence)
- Retrievers — Similarity search, MMR
- Baseline RAG agent — LangChain + OpenAI gpt-4o-mini
- Mini eval set — 10 manually verified questions with keyword hit rate

### Embeddings comparison
| Model                         | Dims | Cost                  | Speed (63 chunks) |
|-------------------------------|------|-----------------------|-------------------|
| OpenAI text-embedding-3-small | 1536 | ~$0.00002/1k tokens   | 0.97s             |
| BGE-base-en-v1.5 (MPS)        | 768  | Free                  | ~1.5s             |
| BGE-small-en-v1.5 (CPU)       | 384  | Free                  | 3.80s             |

**Finding:** OpenAI embeddings return more precise results. BGE-base on Apple MPS is a good free alternative for local development.

### Splitters comparison
| Splitter                       | Chunks | Based on          |
|--------------------------------|--------|-------------------|
| RecursiveCharacterTextSplitter | 74     | Size + separators |
| CharacterTextSplitter          | 74     | Fixed separator   |
| TokenTextSplitter              | 92     | Token count       |
| SemanticChunker                | 62     | Meaning change    |

**Finding:** SemanticChunker produces fewest chunks (62) because it groups related sentences together. TokenTextSplitter produces most chunks (92) because 200 tokens ≈ 800 chars which is smaller than 1000 char chunks.

### Retriever comparison
| Retriever        | Best for                          | Weakness                        |
|------------------|-----------------------------------|---------------------------------|
| Similarity (k=3) | Focused factual queries           | Redundant results, lexical bias |
| MMR (k=3, fk=15) | Broad queries needing coverage    | Over-diversity on simple queries|

**Finding:** MMR fixed the ID 9 lexical overlap failure by fetching diverse candidates. For this document both tied at 0.88.

### Eval set findings
| ID | Question                        | Similarity | MMR  | Notes                          |
|----|---------------------------------|------------|------|--------------------------------|
| 1  | Task decomposition              | 1.00       | 1.00 |                                |
| 2  | ReAct framework                 | 1.00       | 1.00 |                                |
| 3  | Chain of thought                | 1.00       | 1.00 |                                |
| 4  | Three components of LLM agent   | 1.00       | 1.00 |                                |
| 5  | Generative Agents               | 1.00       | 1.00 |                                |
| 6  | Self reflection                 | 0.67       | 0.33 | Keywords too specific          |
| 7  | Short vs long term memory       | 1.00       | 1.00 |                                |
| 8  | Tree of Thoughts                | 1.00       | 1.00 |                                |
| 9  | LLM agents external APIs        | 0.00       | 1.00 | Lexical overlap, MMR fixed it  |
| 10 | MIPS                            | 1.00       | 1.00 |                                |
|    | **Average**                     | **0.88**   | **0.88** |                            |

### Limitation of keyword eval
Keyword matching fails when meaning is correct but exact keywords differ. Example: chunk says "ability to run code" but keyword is "code execution" → score 0. RAGAS semantic evaluation fixes this in Week 4 by using LLM to judge meaning not keywords.

---

## Week 4 — CRAG + Self-RAG + Apple 10-K Eval

### RAGAS Evaluation (blog post)
| Pipeline    | Faithfulness | Context Recall | Factual Correctness |
|-------------|-------------|----------------|---------------------|
| Vanilla RAG | 0.85        | 0.75           | 0.58                |
| CRAG        | 0.94        | 0.80           | 0.52                |
| Self-RAG    | 0.83        | 0.80           | 0.46                |
| Combined    | 0.87        | 0.60           | 0.49                |

**Key findings:**
- CRAG achieves highest faithfulness (0.94) by filtering irrelevant chunks before generation
- Combined pipeline shows lower context recall (0.60) due to double filtering: ~70% × 70% ≈ 49% of relevant chunks survive both passes
- Vanilla RAG highest factual correctness (0.58) — uses all chunks including borderline ones
- CRAG is best choice for financial Q&A where grounded answers matter most

### What was built
- CRAG with LangGraph — retrieval quality guard
- Self-RAG with LangGraph — generation quality guard
- Combined CRAG + Self-RAG — unified pipeline
- Refactored into OOP classes (VanillaRAG, CRAGPipeline, SelfRAGPipeline, CombinedRAGPipeline)
- LangSmith tracing — token cost and latency per node
- RAGAS evaluation pipeline

### Apple 10-K Eval Set
Generated 100-question golden eval set from Apple FY2025 10-K filing:
- Downloaded directly from SEC EDGAR (required custom User-Agent header)
- Split into 151 chunks (chunk_size=1500, overlap=200)
- Used SingleHopSpecificQuerySynthesizer (multi-hop synthesizer has a known RAGAS 0.3.3 bug with NER-based theme extraction returning tuples instead of strings — deferred to a later week)
- Cleanup: exact + semantic dedup (threshold=0.92), 1 unanswerable question kept as hallucination test case
- Manually caught and fixed 2 ground-truth errors during verification:
  - Shareholders' equity question had wrong year's figure ($73,733M vs correct $56,950M for Sept 28, 2024)
  - Product-release question was missing "Mac Studio" from its answer
- Final set: 99 questions + 1 hallucination test case

### RAGAS Results (20-question subset, Apple 10-K)
| Pipeline   | Faithfulness | Context Recall | Factual Correctness |
|------------|-------------|----------------|---------------------|
| VanillaRAG | 0.87        | 1.00           | 0.71                |
| CRAG       | 0.93        | 0.95           | 0.68                |
| SelfRAG    | 0.86        | 1.00           | 0.61                |
| Combined   | 0.75        | 0.78           | 0.50                |

**Key findings:**

1. **Chunking strategy affects retrieval quality in dense sections.** The Services section of the 10-K lists 8+ sub-services in rapid succession. At chunk_size=1500, a single chunk spans 6-8 topics, diluting the embedding. Smaller chunks or semantic chunking would improve precision. (Week 7 Docling candidate.)

2. **Combined pipeline underperforms on every metric — a real finding, not a bug.** Sequential CRAG + Self-RAG filters compound: ~70% × 70% ≈ 49% of relevant chunks survive. Result: lowest context recall (0.78), faithfulness (0.75), and factual correctness (0.50).

3. **CRAG alone remains the most faithful pipeline** (0.93) — single relevance-grading step filters bad chunks without over-pruning.

### Multi-hop Questions (Deferred)
RAGAS 0.3.3 multi-hop synthesizer has a pydantic validation bug. For a single-document eval set, multi-hop is less critical — true value emerges in Week 8+ when comparing across multiple companies' filings.

---

## Week 5 — Security + Reliability

### Retry logic (tenacity)
Wrapped `BaseRAGPipeline.run()` with exponential backoff retry (3 attempts, 1-10s wait) to handle transient API failures without crashing eval runs.

**Hard bug found:** the retry decorator masked a TypeError (list called as function) by succeeding on retry after Redis had already cached the answer from attempt 1. Correct answer returned but for the wrong reason — caught only by reading the double-print in output (`[CACHE MISS]` then `[EXACT CACHE HIT]` for a single call).

### Caching (Redis)
**Exact-match cache:** keyed by `hash(dataset_name + pipeline_class + normalized_question)`. Namespacing by both dataset AND pipeline class was essential — without it, all 4 pipelines collided on identical questions and returned whichever pipeline answered first. 24h TTL prevents stale answers when underlying filings update.

**Semantic cache:** cosine similarity over question embeddings (threshold=0.90) + number-extraction guard (`_extract_numbers`).

**Key finding:** dense embeddings rank "same phrasing, different year" pairs as MORE similar (0.947) than "different phrasing, same year" pairs (0.933). Without the number-guard, a naive semantic cache returns 2025's net income ($112,010M) for a 2024 question ($93,736M). The guard checks numeric tokens match before allowing a semantic hit.

### Auth (JWT + RBAC)
- `auth.py`: HS256 token creation/verification, 1-hour expiry, tamper detection via signature validation
- `rbac.py`: role→permission mapping (admin/user/guest), `check_access(token, permission)` — ready for Week 7 FastAPI wiring

### Encryption (AES-256-GCM)
256-bit key, 96-bit nonce, built-in authentication tag (no separate HMAC needed). Validated encrypt/decrypt round-trip and tamper detection (`InvalidTag` on modified ciphertext). Pattern for encrypting user-provided API keys before database storage (Week 8+).

**Distinction:** MD5/SHA256 used in cache keys = hashing (one-way, for consistent key generation). AES-256-GCM = encryption (two-way, for protecting sensitive data at rest). Different tools for different problems.

---

## Week 6 — Scale + Advanced Retrieval

### Pinecone Migration (FAISS → Pinecone Serverless)
Migrated from local in-memory FAISS to Pinecone serverless (us-east-1, AWS, cosine metric, 1536 dims). 151 Apple 10-K chunks ingested with `text-embedding-3-small`. Index persists across sessions — no rebuild cost on every script run.

### Hybrid Search: BM25 + Dense + RRF Fusion
```python
rrf_score(chunk) = 1/(k + dense_rank) + 1/(k + bm25_rank)
# k=60 — standard constant dampening outlier ranks
```

RRF chosen over weighted score averaging: ranks are comparable across retrievers (BM25 score of 5.2 and cosine similarity of 0.67 are not on the same scale — ranks are).

### Reranking: Cohere rerank-english-v3.0
Precision layer on top of RRF — retrieve top 10 via RRF, rerank, return top 3:

| Query | Dense #1 | RRF #1 | Reranked #1 |
|-------|----------|--------|-------------|
| Net income 2025 | ❌ deferred revenue | ⚠️ gross margin | ✅ Statements of Operations (0.9981) |
| Main risk factors | ✅ cybersecurity risk | ❌ investor relations | ⚠️ investor relations (chunking issue) |
| Q2 2025 products | ❌ stock graph | ✅ product list | ✅ product list (0.9964) |

**Key finding:** reranker surfaced "Net income $112,010M" at #1 from being completely absent in dense-only top 3 — retrieval solves recall, reranking solves precision.

### Chunking Experiment: chunk_size=800 vs 1500
Smaller chunks (800 chars → 280 chunks) performed **worse** across all queries. Root cause: Apple's 10-K has two fundamentally different section types: