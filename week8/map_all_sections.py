"""
from extract_sections_v3 import (normalize_table_noise,ITEM_KEYWORDS,has_toc_anchor,has_negative_context,NEGATIVE_PATTERN)
import re
ITEM_ORDER = ["1", "1A", "1B", "1C", "2", "3", "4", "5", "6", "7", "7A", "8",
              "9", "9A", "9B", "9C", "10", "11", "12", "13", "14", "15", "16"]

def is_page_number_toc(text,match_end):
    following=text[match_end:match_end+80].strip()
    if re.match(r"^[\d\s,\-–—]+(?:[A-Z]|$)", following):
        return True
    # also catch "Not Applicable" / "None" immediately after (TOC placeholder listings)
    if re.match(r"^(?:not\s+applicable|none)\b", following, re.IGNORECASE):
        return False  # this is actually a real (empty) section, keep it
    return False

def find_real_heading_start(text,item,search_from=0):
    kw=ITEM_KEYWORDS[item]

    for m in re.finditer(kw,text[search_from:],re.IGNORECASE):
        abs_start=search_from+m.start()
        abs_end=search_from+m.end()

        if has_toc_anchor(text,abs_start,abs_end):
            continue
        if is_page_number_toc(text,abs_end):
            continue
        if has_negative_context(text,abs_start,abs_end):
            continue
        following=text[abs_end:abs_end+60]
        if NEGATIVE_PATTERN.search(following):
            continue
        return abs_start
    return None
def map_sections(company):
    with open(f"week8/.cache/filings/{company}_docling_full.md", "r", encoding="utf-8") as f:
        text = normalize_table_noise(f.read())

    print(f"\n{'='*60}\n{company} (len={len(text)})\n{'='*60}")

    positions={}
    search_from=0

    for item in ITEM_ORDER:
        pos=find_real_heading_start(text,item,search_from)
        positions[item]=pos
        if pos is not None:
            search_from=pos+50

    found_items=[(item,pos) for item,pos in positions.items() if pos is not None]
    for i,(item,pos) in enumerate(found_items):
        end=found_items[i+1][1] if i+1<len(found_items) else len(text)
        length=end-pos
        preview = text[pos:pos+70].strip().replace("\n", " ")
        print(f"  Item {item}: pos={pos:>8} len={length:>8}  {preview}")

for company in ["Apple","Morgan_Stanley", "Citigroup"]:
    map_sections(company)

"""
from extract_sections_v3 import normalize_table_noise, ITEM_KEYWORDS, has_toc_anchor, NEGATIVE_PATTERN
import re

text = normalize_table_noise(open("week8/.cache/filings/Citigroup_docling_full.md", "r", encoding="utf-8").read())
kw = ITEM_KEYWORDS["1B"]

for m in re.finditer(kw, text, re.IGNORECASE):
    s, e = m.start(), m.end()
    if 42000 < s < 231054:
        line_start = text.rfind("\n", 0, s) + 1
        line_end = text.find("\n", e)
        if line_end == -1:
            line_end = len(text)
        line = text[line_start:line_end].strip()
        token_count = len(line.split())
        toc_anchor = has_toc_anchor(line) if 'has_toc_anchor' in globals() else False
        print(f"pos={s} token_count={token_count} toc_anchor={toc_anchor}")
        print(f"  neg_before: {bool(NEGATIVE_PATTERN.search(text[max(0,s-60):s]))}")
        print(f"  neg_after:  {bool(NEGATIVE_PATTERN.search(text[e:e+60]))}")
        print(f"  line: {line!r}")
        print(f"  context: {repr(text[s-40:e+60])}")
        print()
