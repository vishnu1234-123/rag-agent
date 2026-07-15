from extract_sections_v2 import normalize_table_noise,is_valid_section_match,ITEM_KEYWORDS,SECTION_MIN_LENGTHS,DEFAULT_MIN_LENGTH
import re

with open("week8/.cache/filings/Morgan_Stanley_docling_full.md","r",encoding="utf-8") as f:
    raw_text=f.read()

text=normalize_table_noise(raw_text)
doc_length=len(text)
kw=ITEM_KEYWORDS["1A"]
min_len=SECTION_MIN_LENGTHS.get("1A",DEFAULT_MIN_LENGTH)
candidates=list(re.finditer(kw,text,re.IGNORECASE))

print(f"Total candidates:{len(candidates)},min_length required:{min_len}\n")

for i,m in enumerate(candidates):
    next_boundary=len(text)

    for other_num,other_kw in ITEM_KEYWORDS.items():
        if other_num=="1A":
            continue
        nm=re.search(other_kw,text[m.end():])
        if nm:
            next_boundary=min(next_boundary,m.end()+nm.start())
    valid=is_valid_section_match(text,m.start(),m.end(),next_boundary,doc_length,"1A",kw)
    section_len=next_boundary-m.end()
    context_before=repr(text[max(0,m.start()-40):m.start()])
    print(f"[{i}] pos={m.start()} valid={valid} content_len={section_len} before={context_before}")

    if valid:
        print(f"     *** THIS ONE WON (first valid=True, loop stops here) ***")
        break