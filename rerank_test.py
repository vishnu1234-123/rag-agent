"""
Rerank diagnostic for the 'reasons for revenue change' failure.

For CVX (declined) and XOM (soft-answered), show:
  - top passages BEFORE rerank (embedding order)
  - top passages AFTER rerank (cross-encoder order)
  - the generated answer from each ordering (top-N passages)

Judge NOT just 'did it answer' but 'did rerank surface the concrete
revenue-change narrative, or just reshuffle general-factor boilerplate?'
"""
from filingsiq.retrieve.prose import retrieve
from filingsiq.retrieve.rerank import rerank
from filingsiq.generate.prose_generate import generate


def show(tag, parents, n=5):
    print(f"  {tag}")
    for p in parents[:n]:
        sec = str(p.get("section_item", "?"))
        sc = p.get("rerank_score", p.get("best_score", 0))
        preview = (p["text"] or "")[:110].replace("\n", " ")
        print(f"    sec={sec:6} score={sc:.3f}  {preview}")


NAMES = {"CVX": "Chevron", "XOM": "ExxonMobil"}

def run(ticker):
    q = f"What reasons does {NAMES[ticker]} give for its revenue change?"
    print("=" * 78)
    print(f"{ticker}: {q}")
    out = retrieve(q, tickers=ticker, form="10-K")
    parents = out["parents"]
    print(f"  retrieved {len(parents)} parents")

    # BEFORE rerank
    show("BEFORE (embedding order):", parents)
    g_before = generate(q, parents)
    print(f"  -> BEFORE generate: declined={g_before['declined']}")

    # AFTER rerank
    reranked = rerank(q, parents)
    show("AFTER (cross-encoder order):", reranked)
    g_after = generate(q, reranked)
    print(f"  -> AFTER generate:  declined={g_after['declined']}")
    if not g_after["declined"]:
        print("  AFTER answer:", g_after["answer"][:400].replace("\n", " "))
    print()


if __name__ == "__main__":
    # map to the real tickers/names the corpus uses
    for t in ["CVX", "XOM"]:
        run(t)