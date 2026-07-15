# week8/test_normalize_all.py
from normalize_markdown import normalize_table_noise
from extract_sections import extract_section  # or extract_all_sections, whichever you kept
import re
"""
for company in ["Amazon", "Citigroup", "General_Electric", "Apple", "Boeing"]:
    with open(f"week8/.cache/filings/{company}_docling_full.md", "r", encoding="utf-8") as f:
        raw_text = f.read()

    cleaned = normalize_table_noise(raw_text)
    sections = extract_section(cleaned)
    print(f"{company}: {len(sections)} sections -> {sorted(sections.keys())}")
"""

with open("week8/.cache/filings/Morgan_Stanley_docling_full.md", "r", encoding="utf-8") as f:
    text = f.read()

cleaned = normalize_table_noise(text)

# search for the specific real-heading pattern we saw at 4.1% in the raw diagnostic
idx = cleaned.find("For a discussion of the risks and uncertainties that may affect our")
print(repr(cleaned[max(0, idx-300):idx+100]))

window_size=3000
step=1500
best_windows=[]

for i in range(0,len(text)-window_size,step):
    window=text[i:i+window_size]
    count=len(re.findall(r"\brisk\b",window,re.IGNORECASE))
    if count>15:
        best_windows.append((i,count))

print(f"Found {len(best_windows)} dense-risk windows")
for pos, count in best_windows[:5]:
    pct = (pos / len(text)) * 100
    print(f"\nAt {pct:.1f}% (count={count}):")
    print(repr(text[pos:pos+300]))
