from extract_sections_v2 import normalize_table_noise,pass1_item_number,pass2_markdown_heading,ITEM_KEYWORDS
import re
company="Morgan_Stanley"

with open(f"week8/.cache/filings/{company}_docling_full.md", "r", encoding="utf-8") as f:
    raw_text = f.read()

text = normalize_table_noise(raw_text)
print(f"Normalized text length: {len(text)}")


sections_p1=pass1_item_number(text)
print(f"\n---PASS 1 (ITEM N + Title) ---")
print(f"Found: {sorted(sections_p1.keys())}")
for num, content in sections_p1.items():
    print(f"  Item {num}: {len(content)} chars, starts: {repr(content[:80])}")

all_items = {"1", "1A", "1B", "1C", "2", "3", "4", "5", "6", "7", "7A", "8", "9", "9A", "9B", "9C", "10", "11", "12", "13", "14", "15", "16"}
missing_after_p1 = all_items - set(sections_p1.keys())
print(f"\nMissing after Pass 1: {sorted(missing_after_p1)}")

sections_p2 = pass2_markdown_heading(text, missing_after_p1)
print(f"\n--- PASS 2 (markdown heading, no item number) ---")
print(f"Found: {sorted(sections_p2.keys())}")
for num, content in sections_p2.items():
    print(f"  Item {num}: {len(content)} chars, starts: {repr(content[:80])}")

missing_after_p2 = missing_after_p1 - set(sections_p2.keys())
print(f"\nStill missing after Pass 2: {sorted(missing_after_p2)}")


kw=ITEM_KEYWORDS["1A"]
candidates=list(re.finditer(kw,text,re.IGNORECASE))
print(f"Total candidates for 'risk factors':{len(candidates)}")

for i, m in enumerate(candidates):
    context_before = text[max(0, m.start()-40):m.start()]
    print(f"\n[{i}] pos={m.start()} before: {repr(context_before[-40:])}")