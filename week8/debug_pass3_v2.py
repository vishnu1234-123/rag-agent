from extract_sections_v2 import normalize_table_noise, find_next_real_boundary, is_valid_section_match, ITEM_KEYWORDS
import re

with open("week8/.cache/filings/Morgan_Stanley_docling_full.md", "r", encoding="utf-8") as f:
    raw_text = f.read()
text = normalize_table_noise(raw_text)
doc_length = len(text)

kw = ITEM_KEYWORDS["1A"]
candidates = list(re.finditer(kw, text, re.IGNORECASE))

for i, m in enumerate(candidates):
    next_boundary = find_next_real_boundary(text, m.end(), "1A")
    valid = is_valid_section_match(text, m.start(), m.end(), next_boundary, doc_length, "1A", kw)
    section_len = next_boundary - m.end()
    print(f"[{i}] pos={m.start()} valid={valid} content_len={section_len}")
    if valid:
        print(f"  *** WON *** preview: {repr(text[m.start():m.start()+200])}")
        break
