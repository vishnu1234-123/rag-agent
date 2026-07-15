from extract_sections_v2 import normalize_table_noise,is_valid_section_match,ITEM_KEYWORDS

import re

with open("week8/.cache/filings/Morgan_Stanley_docling_full.md","r",encoding="utf-8") as f:
    raw_text=f.read()
text=normalize_table_noise(raw_text)

kw=ITEM_KEYWORDS["1A"]
candidates=list(re.finditer(kw,text,re.IGNORECASE))

for idx in [0,2,4,13]:
    m= candidates[idx]
    next_boundary=len(text)
    for other_num,other_kw in ITEM_KEYWORDS.items():
        if other_num=="1A":
            continue
        nm=re.search(other_kw,text[m.end():])
        if nm:
            next_boundary=min(next_boundary,m.end()+nm.start())
    valid = is_valid_section_match(text,m.start,m.end(),next_boundary,min_length=1000)
    section_len=next_boundary-m.end()
    print(f"Candidate [{idx}] at pos {m.start()}: valid={valid}, content_length_to_next_boundary={section_len}")


