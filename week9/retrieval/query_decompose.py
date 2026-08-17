import os,sys,json
from pathlib import Path
from dotenv import load_dotenv

_HERE=Path(__file__).resolve()
load_dotenv(_HERE.parent.parent.parent/".env")
load_dotenv()
from openai import OpenAI

_oai=OpenAI()
DECOMPOSE_MODEL="gpt-4o-mini"

_SYSTEM = (
    "You break complex questions about SEC filings into simple, focused, "
    "self-contained sub-questions, each answerable on its own.\n"
    "Rules:\n"
    "- Each sub-question must name its specific company explicitly (never each "
    "or both — expand those into one sub-question per company).\n"
    "- Separate a NUMERIC ask (figures, growth, comparison of numbers) from a "
    "PROSE ask (reasons, explanations, factors, risks) into different sub-questions.\n"
    "- For PROSE sub-questions (reasons/factors/risks), do NOT include specific "
    "years or date ranges. Narrative filings are not year-indexed, so a year "
    "qualifier causes false mismatches. Ask for the reasons or factors plainly.\n"
    "- Keep sub-questions minimal and searchable.\n"
    'Return ONLY JSON with this EXACT key: {"sub_questions": ["...", "..."]}'
)

def decompose(question):
    resp=_oai.chat.completions.create(
        model=DECOMPOSE_MODEL,temperature=0,
        response_format={"type":"json_object"},
        messages=[{"role":"system","content":_SYSTEM},
                {"role":"user","content":f"Question:{question}"}]
    )
    d=json.loads(resp.choices[0].message.content.strip())
    subs = (d.get("sub_questions") or d.get("sub_question")
            or d.get("subquestions") or d.get("questions") or [])
    return [q.strip() for q in subs if q.strip()]
if __name__=="__main__":
    tests = [
        "Between Chevron and ExxonMobil, which grew revenue faster from fiscal "
        "2021 to 2025, and what reasons does each give for its revenue change?",
        "What was Apple's 2024 net income, and what risks did they flag?",
    ]
    for q in tests:
        print("\nQ:", q)
        for sq in decompose(q):
            print("  -", sq)