import re

# -----normaliztion ------

def normalize_table_noise(text:str)->str:
    text=re.sub(r"\|"," ",text)
    text=re.sub(r"[ \t]{2,}"," ",text)
    text=re.sub(r"\b(/{3,40}?)(\s*\1){1,}"," ",text,flags=re.IGNORECASE)

    return text

# ---- Item N+ Title(primary) -----

ITEM_KEYWORDS = {
    "1": r"business", "1A": r"risk\s*factors", "1B": r"unresolved\s*staff\s*comments",
    "1C": r"cybersecurity", "2": r"properties", "3": r"legal\s*proceedings",
    "4": r"mine\s*safety\s*disclosures", "5": r"market\s*for\s*registrant",
    "6": r"reserved|selected\s*financial\s*data", "7": r"management.{0,3}s?\s*discussion",
    "7A": r"quantitative\s*and\s*qualitative", "8": r"financial\s*statements\s*and\s*supplementary",
    "9": r"changes\s*in\s*and\s*disagreements", "9A": r"controls\s*and\s*procedures",
    "9B": r"other\s*information", "9C": r"disclosure\s*regarding\s*foreign",
    "10": r"directors,?\s*executive\s*officers", "11": r"executive\s*compensation",
    "12": r"security\s*ownership", "13": r"certain\s*relationships",
    "14": r"principal\s*account(?:ant|ing)", "15": r"exhibits", "16": r"form\s*10-k\s*summary",
}

def build_item_pattern():
    parts = [rf"item\s*{num}\.?\s*(?:{kw})" for num, kw in ITEM_KEYWORDS.items()]
    return re.compile(rf"\b(?:{'|'.join(parts)})",re.IGNORECASE)

ITEM_PATTERN=build_item_pattern()
ITEM_NUM_EXTRACT=re.compile(r"item\s*(\d{1,2}[a-c]?)", re.IGNORECASE)

def pass1_item_number(text:str)->dict:
    matches=list(ITEM_PATTERN.finditer(text))
    sections={}
    for i,m in enumerate(matches):
        print(i,m)
        num=ITEM_NUM_EXTRACT.search(m.group()).group(1).upper()
        start,end=m.start(),(matches[i+1].start() if i+1<len(matches) else len(text))
        if num not in sections or (end-start)>len(sections[num]):
            sections[num]=text[start:end]

    return sections

def build_heading_pattern():
    parts = [rf"^#+\s*(?:{kw})\s*$" for kw in ITEM_KEYWORDS.values()]
    return re.compile(rf"(?:{'|'.join(parts)})",re.IGNORECASE|re.MULTILINE)

HEADING_PATTERN=build_heading_pattern()
KEYWORD_TO_ITEM={kw:num for num,kw in ITEM_KEYWORDS.items()}

def pass2_markdown_heading(text:str,missing_items:set)->dict:
    matches=list(HEADING_PATTERN.finditer(text))
    sections={}
    for i,m in enumerate(matches):
        matched_text=m.group().lower()
        for kw,num in KEYWORD_TO_ITEM.items():
            if num in missing_items and re.search(kw,matched_text,re.IGNORECASE):
                start,end=m.start(),(matches[i+1].start() if i+1<len(matches) else len(text))
                if num not in sections (end-start)>len(sections[num]):
                    sections[num]=text[start:end]
    return sections

def is_toc_entry(text:str,match_start:int,match_end:int)->bool:
    context_before=text[max(0,match_start-40):match_start]
    context_after=text[match_end:match_end+60]

    if re.search(r"\]\(#\w+\)",context_before) or re.search(r"\]\(#\w+\)",context_after):
        return True
    if re.search(r"#\w{10,}",context_before):
        return True
    return False

SECTION_MIN_PERCENTAGE = {
    "1": 0.02, "1A": 0.05, "1B": 0.0001, "1C": 0.001,
    "7": 0.03, "7A": 0.005, "8": 0.05,
}
DEFAULT_SECTION_PERCENTAGE = 0.005
ABSOLUTE_FLOOR = 100

def get_min_length_threshold(doc_length:int,item_num:str)->int:
    pct=SECTION_MIN_PERCENTAGE.get(item_num,DEFAULT_SECTION_PERCENTAGE)
    return max(ABSOLUTE_FLOOR,int(doc_length*pct))

NEGATIVE_PATTERN = re.compile(
    r'see\b|refer\b|detailed\s+under|discussed\s+(?:above|below|herein)|described\s+(?:in|under)|"\s*,\s*"|and\s+elsewhere',
    re.IGNORECASE
)

def has_nearby_other_keyword(text:str,match_end:int,current_keyword:str,window:int=150)->bool:
    nearby=text[match_end:match_end+window]
    other_keywords=[kw for k,kw in ITEM_KEYWORDS.items() if kw!=current_keyword]
    return any(re.search(kw,nearby,re.IGNORECASE) for kw in other_keywords)

def find_next_real_boundary(text:str,search_from:int,current_item:str)->int:
    remaining_items=[num for num in ITEM_KEYWORDS if num!=current_item]

    best_boundary=len(text)

    for other_num in remaining_items:
        other_kw=ITEM_KEYWORDS[other_num]
        for m in re.finditer(other_kw,text[search_from:],re.IGNORECASE):
            abs_start=search_from+m.start()
            abs_end=search_from+m.end()
            if is_toc_entry(text,abs_start,abs_end):
                continue
            context_before=text[max(0,abs_start-60):abs_start]
            if NEGATIVE_PATTERN.search(context_before):
                continue
            if not looks_like_heading(text,abs_start,abs_end):
                continue
            if abs_start<best_boundary:
                best_boundary=abs_start
            break
    return best_boundary

def looks_like_heading(text:str,match_start:int,match_end:int)->bool:
    line_start=text.rfind("\n",0,match_start)+1
    prefix_on_line=text[line_start:match_start].strip()

    line_end=text.find("\n",match_end)
    if line_end== -1:
        line_end=len(text)
    suffix_on_line=text[match_end:line_end].strip()

    return len(prefix_on_line)<5 and len(suffix_on_line)<60

def is_valid_section_match(text:str,match_start:int,match_end:int,next_boundary:int,doc_length,item_num,current_keyword,min_paragraphs:int=3,min_gap:int=800)->bool:
    if is_toc_entry(text,match_start,match_end):
        return False
    min_length=get_min_length_threshold(doc_length,item_num)
    section_text=text[match_start:next_boundary]

    #prose length
    if len(section_text.strip())<min_length:
        return False
    
    #negative patterns 
    context_before=text[max(0,match_start-60):match_start].lower()
    context_after=text[match_end:match_end+60]

    if NEGATIVE_PATTERN.search(context_before) or NEGATIVE_PATTERN.search(context_after):
        return False
    if has_nearby_other_keyword(text,match_end,current_keyword):
        return False
        
    paragraph_count=len([p for p in section_text.split("\n\n") if len(p.strip())>50])
    if paragraph_count<min_paragraphs:
        return False
    
    if (next_boundary-match_end)<min_gap:
        return False
    
    return True


SECTION_MIN_LENGTHS={
    "1A":1000,"7":1500,"1":1200
}
DEFAULT_MIN_LENGTH=800
def pass3_bare_keyword(text:str,missing_items:set)->dict:
    sections={}
    for num in missing_items:
        kw=ITEM_KEYWORDS.get(num)
        if not kw:
            continue
        min_len=SECTION_MIN_LENGTHS.get(num,DEFAULT_MIN_LENGTH)
        candidates=list(re.finditer(kw,text,re.IGNORECASE))

        for m in candidates:
            next_boundary=find_next_boundary(text,m.end(),num)
            
            if is_valid_section_match(text,m.start(),m.end(),next_boundary,min_len):
                sections[num]=text[m.start():next_boundary]
                break
    return sections

        

def split_into_sections_v2(raw_text: str) -> dict:
    text = normalize_table_noise(raw_text)
    sections = pass1_item_number(text)

    all_items = set(ITEM_KEYWORDS.keys())
    missing = all_items - set(sections.keys())
    if missing:
        sections.update(pass2_markdown_heading(text, missing))

    missing = all_items - set(sections.keys())
    if missing:
        sections.update(pass3_bare_keyword(text, missing))

    return sections






