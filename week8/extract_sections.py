import re

# Loose keyword patterns per item, built from REAL variants observed across our 20 companies.
# Add more alternatives here (pipe-separated) as new companies surface new phrasing.
ITEM_KEYWORDS = {
    "1": r"business",
    "1A": r"risk\s*factors",
    "1B": r"unresolved\s*staff\s*comments",
    "1C": r"cybersecurity",
    "2": r"properties",
    "3": r"legal\s*proceedings",
    "4": r"mine\s*safety\s*disclosures",
    "5": r"market\s*for\s*registrant",
    "6": r"reserved|selected\s*financial\s*data",
    "7": r"management.{0,3}s?\s*discussion",  # handles ' vs ' vs missing apostrophe
    "7A": r"quantitative\s*and\s*qualitative",
    "8": r"financial\s*statements\s*and\s*supplementary",
    "9": r"changes\s*in\s*and\s*disagreements",
    "9A": r"controls\s*and\s*procedures",
    "9B": r"other\s*information",
    "9C": r"disclosure\s*regarding\s*foreign",
    "10": r"directors,?\s*executive\s*officers",
    "11": r"executive\s*compensation",
    "12": r"security\s*ownership",
    "13": r"certain\s*relationships",
    "14": r"principal\s*account(?:ant|ing)",
    "15": r"exhibits",
    "16": r"form\s*10-k\s*summary",
}

def build_item_pattern():
    parts=[rf"item\s*{num}\.?\s*(?:{kw})" for num, kw in ITEM_KEYWORDS.items()]
    combined="|".join(parts)
    return re.compile(rf"\b(?:{combined})", re.IGNORECASE)

ITEM_PATTERN=build_item_pattern()
ITEM_NUM_EXTRACT=re.compile(r"item\s*(\d{1,2}[a-c]?)", re.IGNORECASE)

def extract_section(markdown_text:str)->dict[str,str]:
    matches=list(ITEM_PATTERN.finditer(markdown_text))
    sections={}

    for i,match in enumerate(matches):
        num_match=ITEM_NUM_EXTRACT.search(match.group())
        item_num=num_match.group(1).upper()
        start=match.start()
        end=matches[i+1].start() if i+1<len(matches) else len(markdown_text)
        if item_num not in sections or (end-start)>len(sections[item_num]):
            sections[item_num]=markdown_text[start:end]
    return sections
    