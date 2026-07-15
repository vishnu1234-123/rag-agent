# week8/test_scoring.py
from extract_sections_v3 import split_into_sections_v3

with open("week8/.cache/filings/Morgan_Stanley_docling_full.md", "r", encoding="utf-8") as f:
    text = f.read()

sections, scores = split_into_sections_v3(text, return_scores=True)

for item in ["1", "1A", "1B", "7", "7A"]:
    if item in sections:
        s = scores[item]
        content = sections[item]
        print(f"\nItem {item}: score={s['score']:.1f} confident={s['confident']} len={len(content)}")
        print(f"  breakdown: {s['breakdown']}")
        print(f"  START: {content[:120].strip()}")
    else:
        print(f"\nItem {item}: NOT FOUND")