"""
Quick diagnostic: how does Docling's markdown represent section titles?
Our header regex found ~0 '#' headers despite complete docs, so section
titles must be in another format. This shows us the actual format, which
directly informs the chunking boundary strategy.
"""
import re
from pathlib import Path

# look at Apple's 10-K - we know it's complete
text = Path("data/processed/AAPL/AAPL_10K_full.md").read_text()

print("=== First 60 lines of Apple 10-K markdown ===")
for line in text.splitlines()[:60]:
    if line.strip():
        print(repr(line[:100]))

print("\n=== How does 'Risk Factors' appear? (lines containing it) ===")
for line in text.splitlines():
    if "risk factors" in line.lower():
        print(repr(line[:120]))

print("\n=== Count of different possible header markers ===")
print(f"  '#' markdown headers:     {len(re.findall(r'^#{1,6}\s', text, re.M))}")
print(f"  '**bold**' lines:         {len(re.findall(r'^\*\*.+\*\*\s*$', text, re.M))}")
print(f"  'Item N.' lines:          {len(re.findall(r'(?im)^item\s+\d+[a-z]?\.', text))}")
print(f"  ALL-CAPS heading-ish:     {len(re.findall(r'^[A-Z][A-Z &]{6,}$', text, re.M))}")