from normalize_markdown import normalize_table_noise

with open("week8/.cache/filings/Amazon_docling_full.md","r",encoding="utf-8") as f:
    raw_text=f.read()

cleaned_text=normalize_table_noise(raw_text)

start = int(len(raw_text) * 0.055)
print("BEFORE (raw):")
print(repr(raw_text[start:start+300]))
print("\nAFTER (normalized):")
# find corresponding region in cleaned text by searching for known anchor phrase
idx = cleaned_text.lower().find("please carefully consider")
print(repr(cleaned_text[max(0, idx-200):idx+200]))