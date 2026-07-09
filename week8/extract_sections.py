import re
def extract_section(markdown_text:str,start_pattern:str,end_pattern:str)->str:
    start_match=re.search(start_pattern,markdown_text,re.IGNORECASE)
    if not start_match:
        print(f"WARNING: start pattern not found: {start_pattern}")
        return ""
    start_idx=start_match.start()
    end_match=re.search(end_pattern,markdown_text[start_idx+1:],re.IGNORECASE)

    if not end_match:
        print(f"WARNING: end pattern not found, taking rest of document")
        return markdown_text[start_idx:]
    end_idx=start_idx+1+end_match.start()
    return markdown_text[start_idx:end_idx]

if __name__=="__main__":
    with open("week8/.cache/filings/aaple_10k_docling_output.md","r",encoding="utf-8") as f:
        full_text=f.read()

    risk_factors=extract_section(
        full_text,
        r"item\s*1a\.?\s*risk\s*factors",
        r"item\s*1b\.?\s*unresolved|item\s*2\.?\s*properties"
    )
    print(f"Risk Factors section: {len(risk_factors)} chars")

    mda = extract_section(
        full_text,
        r"item\s*7\.?\s*management.?s\s*discussion",
        r"item\s*7a\.?\s*quantitative|item\s*8\.?\s*financial\s*statements"
    )
    print(f"MD&A section: {len(mda)} chars")

    import os
    os.makedirs("week8/.cache/prose",exist_ok=True)
    with open("week8/.cache/prose/aapl_10k_2025_risk_factors.md", "w", encoding="utf-8") as f:
        f.write(risk_factors)
    with open("week8/.cache/prose/aapl_10k_2025_mda.md", "w", encoding="utf-8") as f:
        f.write(mda)

    print("\nRisk Factors preview:")
    print(risk_factors[:500])
    print("\nMD&A preview:")
    print(mda[:500])
