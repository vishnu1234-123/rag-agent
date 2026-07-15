from extract_sections_v3 import (normalize_table_noise,find_next_boundary,score_candidate,ITEM_KEYWORDS)
import re

with open("week8/.cache/filings/Morgan_Stanley_docling_full.md", "r", encoding="utf-8") as f:
    raw_text = f.read()
text = normalize_table_noise(raw_text)
doc_length = len(text)

kw = ITEM_KEYWORDS["1A"]
candidates = list(re.finditer(kw, text, re.IGNORECASE))

print(f"doc_length={doc_length}, candidates={len(candidates)}\n")

for i,m in enumerate(candidates):
    next_boundary=find_next_boundary(text,m.end(),"1A",doc_length)
    score,breakdown=score_candidate(text,m.start(),m.end(),next_boundary,doc_length,"1A")
    print(f"[{i}] pos={m.start()} score={score:.1f} breakdown={breakdown}")
   

from extract_sections_v3 import normalize_table_noise, ITEM_KEYWORDS
import re

with open("week8/.cache/filings/Morgan_Stanley_docling_full.md", "r", encoding="utf-8") as f:
    text = normalize_table_noise(f.read())

kw = ITEM_KEYWORDS["1A"]
candidates = list(re.finditer(kw, text, re.IGNORECASE))
m = candidates[4]  # the real one at pos 80670

line_start = text.rfind("\n", 0, m.start()) + 1
prefix_on_line = text[line_start:m.start()]
print("PREFIX ON LINE (raw):", repr(prefix_on_line))
print("PREFIX length:", len(prefix_on_line))