"""
Grounded generation over retrieved parent passages.

STRICT grounding: answer ONLY from the provided passages, cite which passage(s),
and DECLINE if the answer is not present. This is the hallucination defense — a
confident "not in the filings" beats a plausible fabrication. Paired with the
prose retriever's high recall (right passage almost always present), strict
generation rarely mis-declines.

Plain OpenAI (gpt-4o-mini), matching the week8/9 stack (no LangChain).
"""
import os, sys
from pathlib import Path
from dotenv import load_dotenv

_HERE = Path(__file__).resolve()
load_dotenv(_HERE.parent.parent.parent / ".env")
load_dotenv()
from openai import OpenAI

_oai = OpenAI()
GEN_MODEL = "gpt-4o-mini"

_SYSTEM = (
    "You answer questions about SEC filings using ONLY the provided passages. "
    "Rules:\n"
    "1. Base your answer STRICTLY on the passages. Do not use outside knowledge.\n"
    "2. If the passages do not contain the answer, reply EXACTLY: "
    "\"I don't find that in the filings.\" Do not guess.\n"
    "3. Be COMPLETE: include ALL relevant factors, reasons, or items the passages\n""   support for the question — do not omit supporting details to be brief.\n""4. Stay factual and cite the passage number(s) you used like [P1], [P2].\n"
    "4. Do not add commentary beyond what the passages support."
)


# Token budget for the context sent to generation. Whole passages are packed
# until the budget is reached — passages are NEVER truncated mid-text, so an
# answer at the END of a large chunk is preserved. Adaptive to chunk size:
# a big chunk consumes more budget, a small one less. Beats a fixed passage
# count + char cap (which loses answers past the cut).
CONTEXT_TOKEN_BUDGET = 7000

try:
    import tiktoken
    _enc = tiktoken.get_encoding("cl100k_base")
    def _ntok(t): return len(_enc.encode(t))
except Exception:
    _enc = None
    def _ntok(t): return len(t) // 4    # ~4 chars/token fallback


def _build_context(parents, budget=CONTEXT_TOKEN_BUDGET, max_passages=None):
    """Pack whole parent passages up to a TOKEN budget (no mid-passage truncation).

    max_passages optionally caps count too, but the budget is the real control.
    Always includes at least the top passage even if it alone exceeds budget.
    """
    blocks, used = [], 0
    for i, p in enumerate(parents, 1):
        if max_passages and i > max_passages:
            break
        text = p["text"] or ""
        n = _ntok(text)
        if used + n > budget and blocks:      # budget hit — stop (keep >=1)
            break
        tag = f"[P{i}] ({p.get('ticker','?')} {p.get('section_item','')})"
        blocks.append(f"{tag}\n{text}")
        used += n
    return "\n\n".join(blocks)

def rewrite_query(question):
    resp=_oai.chat.completions.create(
        model=GEN_MODEL,temperature=0,
        messages=[
            {"role":"system","content":
            "Rewrite the user's question as a short declarative statement phrased "
            "the way a 10-K filing would state the underlying fact, so it matches "
            "filing text for retrieval. Keep it under 40 words. Output ONLY the "
            "rewritten query, no preamble."},
            {"role":"user","content":question},
        ],
    )
    return resp.choices[0].message.content.strip()

def generate(question, parents, max_passages=10):
    """Generate a grounded answer from retrieved parents. Returns answer + meta."""
    if not parents:
        return {"answer": "I don't find that in the filings.",
                "declined": True, "n_passages": 0}

    context = _build_context(parents)
    user = f"Passages:\n\n{context}\n\nQuestion: {question}\n\nAnswer:"

    resp = _oai.chat.completions.create(
        model=GEN_MODEL, temperature=0,
        messages=[{"role": "system", "content": _SYSTEM},
                  {"role": "user", "content": user}],
    )
    answer = resp.choices[0].message.content.strip()
    declined = "don't find that in the filings" in answer.lower()
    return {"answer": answer, "declined": declined,
            "n_passages": min(len(parents), max_passages)}


if __name__ == "__main__":
    sys.path.insert(0, str(_HERE.parent))
    from prose_pipeline import answer_prose
    for q in ["What supply chain risks does Apple face?",
              "What factors are critical for Alphabet to attract and retain advertisers?"]:
        r = answer_prose(q, top_k=10)
        if r["status"] != "retrieved":
            print("DECLINE:", r["message"]); continue
        g = generate(q, r["parents"])
        print(f"\nQ: {q}")
        print(f"declined={g['declined']} passages={g['n_passages']}")
        print(f"A: {g['answer'][:400]}")