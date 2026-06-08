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
