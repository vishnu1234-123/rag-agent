from extract_sections_v3 import normalize_table_noise, ITEM_KEYWORDS
import re

with open("week8/.cache/filings/Citigroup_docling_full.md", "r", encoding="utf-8") as f:
    text = normalize_table_noise(f.read())

kw = ITEM_KEYWORDS["1B"]
matches = list(re.finditer(kw, text, re.IGNORECASE))
print(f"Total 'Unresolved Staff Comments': {len(matches)}")
for m in matches:
    pct = (m.start() / len(text)) * 100
    print(f"  pos={m.start()} ({pct:.1f}%): {repr(text[m.start()-20:m.end()+60])}")

print("END of Item 1A (before 231054):")
print(repr(text[231054-200:231054]))
print("\nSTART of Item 1C (at 231054):")
print(repr(text[231054:231054+200]))