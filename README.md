# RAG Agent — Week 3 Fundamentals

Built as part of the AI Engineer Roadmap (FilingsIQ project).
Baseline RAG pipeline over a web document with retriever comparison and keyword-based evaluation.

## Results
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

## What this covers
- Document loaders — WebBaseLoader, PyPDFLoader
- Text splitters — RecursiveCharacterTextSplitter, CharacterTextSplitter, TokenTextSplitter, SemanticChunker
- Embeddings — OpenAI text-embedding-3-small vs BGE-base-en-v1.5 (local)
- Vector stores — InMemoryVectorStore, FAISS (with persistence)
- Retrievers — Similarity search, MMR
- Baseline RAG agent — LangChain + OpenAI gpt-4o-mini
- Mini eval set — 10 manually verified questions with keyword hit rate

## Embeddings comparison
| Model                         | Dims | Cost                  | Speed (63 chunks) |
|-------------------------------|------|-----------------------|-------------------|
| OpenAI text-embedding-3-small | 1536 | ~$0.00002/1k tokens   | 0.97s             |
| BGE-base-en-v1.5 (MPS)        | 768  | Free                  | ~1.5s             |
| BGE-small-en-v1.5 (CPU)       | 384  | Free                  | 3.80s             |

**Finding:** OpenAI embeddings return more precise results.
BGE-base on Apple MPS is a good free alternative for local development.

## Splitters comparison
| Splitter                       | Chunks | Based on          |
|--------------------------------|--------|-------------------|
| RecursiveCharacterTextSplitter | 74     | Size + separators |
| CharacterTextSplitter          | 74     | Fixed separator   |
| TokenTextSplitter              | 92     | Token count       |
| SemanticChunker                | 62     | Meaning change    |

**Finding:** SemanticChunker produces fewest chunks (62) because it groups
related sentences together. TokenTextSplitter produces most chunks (92)
because 200 tokens ≈ 800 chars which is smaller than 1000 char chunks.

## Retriever comparison
| Retriever        | Best for                          | Weakness                        |
|------------------|-----------------------------------|---------------------------------|
| Similarity (k=3) | Focused factual queries           | Redundant results, lexical bias |
| MMR (k=3, fk=15) | Broad queries needing coverage    | Over-diversity on simple queries|

**Finding:** MMR fixed the ID 9 lexical overlap failure by fetching
diverse candidates. For this document both tied at 0.88.

## Eval set findings
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

## Limitation of keyword eval
Keyword matching fails when meaning is correct but exact keywords differ.
Example: chunk says "ability to run code" but keyword is "code execution" → score 0.
RAGAS semantic evaluation fixes this in Week 4 by using LLM to judge meaning not keywords.

## Stack
- LangChain + LangGraph
- OpenAI (gpt-4o-mini, text-embedding-3-small)
- FAISS vector store
- BGE-base embeddings (local, Apple MPS)
- sentence-transformers
- python-dotenv

## Setup
```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Add your OpenAI key to `.env`:


## Week 4 — CRAG + Self-RAG Results

### RAGAS Evaluation
| Pipeline    | Faithfulness | Context Recall | Factual Correctness |
|-------------|-------------|----------------|---------------------|
| Vanilla RAG | 0.85        | 0.75           | 0.58                |
| CRAG        | 0.94        | 0.80           | 0.52                |
| Self-RAG    | 0.83        | 0.80           | 0.46                |
| Combined    | 0.87        | 0.60           | 0.49                |

**Key findings:**
- CRAG achieves highest faithfulness (0.94) by filtering irrelevant chunks before generation
- Combined pipeline shows lower context recall (0.60) due to double filtering
- Vanilla RAG highest factual correctness (0.58) — uses all chunks including borderline ones
- CRAG is best choice for financial Q&A where grounded answers matter most

### What was built
- CRAG with LangGraph — retrieval quality guard
- Self-RAG with LangGraph — generation quality guard
- Combined CRAG + Self-RAG — unified pipeline
- Refactored into OOP classes (VanillaRAG, CRAGPipeline, SelfRAGPipeline, CombinedRAGPipeline)
- LangSmith tracing — token cost and latency per node
- RAGAS evaluation pipeline


## Week 4 (continued): Apple 10-K Evaluation

### Eval Set Construction
Generated a 100-question golden eval set from Apple's FY2025 10-K filing using RAGAS `TestsetGenerator`:
- Downloaded directly from SEC EDGAR (required custom User-Agent header)
- Split into 151 chunks (chunk_size=1500, overlap=200)
- Used `SingleHopSpecificQuerySynthesizer` (multi-hop synthesizer has a known RAGAS 0.3.3 bug with NER-based theme extraction returning tuples instead of strings — deferred to a later week)

### Cleanup Process
- Removed exact and near-duplicate questions (string normalization + semantic similarity via embeddings, threshold 0.92)
- Flagged 1 "unanswerable" question as an intentional hallucination test case
- Manually caught and fixed 2 ground-truth errors during verification:
  - A shareholders' equity question had the wrong year's figure ($73,733M vs correct $56,950M for Sept 28, 2024)
  - A product-release question was missing "Mac Studio" from its answer
- Final set: 99 questions + 1 hallucination test case

### RAGAS Results (20-question subset, all 4 pipelines)

| Pipeline   | Faithfulness | Context Recall | Factual Correctness |
|------------|-------------|-----------------|----------------------|
| VanillaRAG | 0.87        | 1.00            | 0.71                 |
| CRAG       | 0.93        | 0.95            | 0.68                 |
| SelfRAG    | 0.86        | 1.00            | 0.61                 |
| Combined   | 0.75        | 0.78            | 0.50                 |

### Key Findings

**1. Chunking strategy affects retrieval quality in dense sections.**
The "Services" section of the 10-K lists 8+ sub-services (Advertising, AppleCare, Cloud Services, Apple Music, etc.) in rapid succession. At chunk_size=1500, a single chunk spans 6-8 of these topics, diluting the chunk's semantic embedding and making it harder for any single query to retrieve cleanly. Smaller chunks (500-800) or semantic chunking would likely improve precision for this document type. **(Week 6 tuning candidate.)**

**2. Combined pipeline underperforms on every metric — a real finding, not a bug.**
CRAG and Self-RAG each filter retrieved chunks for relevance. When composed sequentially (Combined), the filters compound: roughly 70% × 70% ≈ 49% of relevant chunks survive both passes. This is most damaging on the "mixed-topic" chunks from Finding 1 — both filters may independently reject a chunk that actually contains the answer, just surrounded by unrelated content. Result: lowest context recall (0.78), faithfulness (0.75), and factual correctness (0.50) of all four pipelines.

**Hypothesis for Week 6:** loosen the second filter's threshold when the first has already filtered, or use OR-logic rather than AND-logic between the two grading steps.

**3. CRAG alone remains the most faithful pipeline** (0.93), consistent with the blog-post eval from earlier in Week 4 — its single relevance-grading step filters out clearly bad chunks without over-pruning.

### Multi-hop Questions (Deferred)
RAGAS 0.3.3's multi-hop synthesizer has a pydantic validation bug (NER overlap returns tuples). For a single-document eval set, multi-hop reasoning is less critical anyway — true multi-hop value emerges in Week 8+ when comparing across multiple companies' filings. Plan: either try a different RAGAS version, or manually write 10-15 cross-section questions (e.g., connecting Risk Factors ↔ MD&A) at that point.
