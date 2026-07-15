from extract_sections_v3 import normalize_table_noise
import re

def show_heading_context(company,known_pos=None):
    with open(f"week8/.cache/filings/{company}_docling_full.md","r",encoding="utf-8") as f:
        text=normalize_table_noise(f.read())
    print(f"\n{'='*60}\n{company}\n{'='*60}")

    if known_pos:
        pos=known_pos
    else:
        m=re.search(r"item\s*1a\.?\s*risk\s*factors", text, re.IGNORECASE)
        pos=m.start() if m else None
    
    if pos is None:
        print("couldn't locate")
        return 
    
    snippet=text[max(0,pos-200):pos+300]
    print(repr(snippet))

show_heading_context("Apple")                        # clean reference
show_heading_context("Morgan_Stanley", known_pos=80670)  # bare-heading problem
show_heading_context("Citigroup")                    # find Citi's real heading