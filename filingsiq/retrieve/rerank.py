"""
Local cross-encoder reranker (optional). No API, no rate limits, no data egress.

Re-scores retrieved parent passages by question-relevance using a local
cross-encoder, then reorders. Toggleable so we can A/B measure whether it earns
its place: if it recovers the buried-passage declines and/or lifts the
reference-mismatch cases, keep it; else delete.

Model: cross-encoder/ms-marco-MiniLM-L-6-v2 (small, fast, CPU-fine, standard
for reranking). Lazy-loaded so importing this file is cheap.
"""
from functools import lru_cache

_MODEL_NAME = "cross-encoder/ms-marco-MiniLM-L-6-v2"


@lru_cache(maxsize=1)
def _model():
    from sentence_transformers import CrossEncoder
    return CrossEncoder(_MODEL_NAME)


def rerank(question, parents, top_k=None):
    """Re-score parents by cross-encoder relevance to the question, reorder desc.

    Cross-encoder scores each (question, passage) pair jointly — far more precise
    than the embedding dot-product used for initial retrieval, because it reads
    the pair together rather than comparing independent vectors. Returns parents
    reordered by rerank_score (original list untouched).
    """
    if not parents:
        return parents
    pairs = [(question, p["text"] or "") for p in parents]
    scores = _model().predict(pairs)
    scored = []
    for p, s in zip(parents, scores):
        p = dict(p)
        p["rerank_score"] = float(s)
        scored.append(p)
    scored.sort(key=lambda r: r["rerank_score"], reverse=True)
    return scored[:top_k] if top_k else scored


if __name__ == "__main__":
    # quick self-test on one question — compare order before/after rerank
    
    from filingsiq.retrieve.prose import retrieve
    q = "What factors are critical for Alphabet to attract and retain advertisers?"
    out = retrieve(q, tickers="GOOGL", top_k=10)
    print("BEFORE rerank (embedding order):")
    for p in out["parents"][:5]:
        print(f"  {p.get('section_item','?'):20} score={p['best_score']:.3f} {p['text'][:60]}")
    rr = rerank(q, out["parents"])
    print("\nAFTER rerank (cross-encoder order):")
    for p in rr[:5]:
        print(f"  {p.get('section_item','?'):20} rr={p['rerank_score']:.3f} {p['text'][:60]}")