import re

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

SECTION_MIN_PERCENTAGE = {
    "1": 0.02, "1A": 0.05, "1B": 0.0001, "1C": 0.001,
    "7": 0.03, "7A": 0.005, "8": 0.05,
}
DEFAULT_SECTION_PERCENTAGE = 0.005
ABSOLUTE_FLOOR = 100

NEGATIVE_PATTERN = re.compile(
    r'see\b|refer\b|detailed\s+under|discussed\s+(?:above|below|herein)|'
    r'described\s+(?:in|under)|"\s*,\s*"|and\s+elsewhere|throughout\s+this\s+report',
    re.IGNORECASE
)


# ============================================================
# Normalization
# ============================================================
def normalize_table_noise(text: str) -> str:
    text = re.sub(r"\|", " ", text)
    text = re.sub(r"[ \t]{2,}", " ", text)
    text = re.sub(r"\b(.{3,40}?)(\s*\1){1,}", r"\1", text, flags=re.IGNORECASE)
    return text

# ============================================================
# Individual signal helpers
# ============================================================
def get_min_length_threshold(doc_length: int, item_num: str) -> int:
    pct = SECTION_MIN_PERCENTAGE.get(item_num, DEFAULT_SECTION_PERCENTAGE)
    return max(ABSOLUTE_FLOOR, int(doc_length * pct))

def has_exact_item_number(text: str, match_start: int) -> bool:
    """Is this match immediately preceded by 'Item N' / 'Item N.'?"""
    prefix = text[max(0, match_start - 12):match_start]
    return bool(re.search(r"item\s*\d{1,2}[a-c]?\.?\s*$", prefix, re.IGNORECASE))

def has_markdown_heading(text: str, match_start: int) -> bool:
    """Is this match on a line that starts with a markdown heading marker (#)?"""
    line_start = text.rfind("\n", 0, match_start) + 1
    line_prefix = text[line_start:match_start]
    return bool(re.match(r"\s*#+\s*(?:item\s*\d{1,2}[a-c]?\.?\s*)?$", line_prefix, re.IGNORECASE))

def has_toc_anchor(text: str, match_start: int, match_end: int) -> bool:
    """Is this match part of a markdown link / TOC anchor pattern?"""
    context = text[max(0, match_start-60):match_end+60]
    return bool(re.search(r"\]\(#\w+\)", context) or re.search(r"#\w{10,}", context))

def looks_like_heading_line(text: str, match_start: int, match_end: int) -> bool:
    """Standalone-heading shape: little before it on the line, short after it."""
    line_start = text.rfind("\n", 0, match_start) + 1
    prefix_on_line = text[line_start:match_start].strip()
    prefix_clean = re.sub(r"(<!--.*?-->|\S+\.jpg|\s|#+)", "", prefix_on_line)
    line_end = text.find("\n", match_end)
    if line_end == -1:
        line_end = len(text)
    suffix_on_line = text[match_end:line_end].strip()
    return len(prefix_clean) < 5 and len(suffix_on_line) < 80

def has_negative_context(text: str, match_start: int, match_end: int) -> bool:
    before = text[max(0, match_start-60):match_start]
    after = text[match_end:match_end+60]
    return bool(NEGATIVE_PATTERN.search(before) or NEGATIVE_PATTERN.search(after))

def has_length_support(text: str, match_end: int, next_boundary: int,
                       doc_length: int, item_num: str, min_paragraphs: int = 3) -> bool:
    section_text = text[match_end:next_boundary]
    if len(section_text.strip()) < get_min_length_threshold(doc_length, item_num):
        return False
    paragraph_count = len([p for p in section_text.split("\n\n") if len(p.strip()) > 50])
    return paragraph_count >= min_paragraphs
WEIGHTS = {
    "exact_item": 5.0,
    "markdown_heading": 4.0,
    "toc_anchor": 4.0,
    "bare_heading_shape": 2.0,
    "negative_context": -3.0,
    "length_support": 1.0,
}
HIGH_THRESHOLD = 4.0
LOW_THRESHOLD = 0.5

def score_candidate(text, match_start, match_end, next_boundary, doc_length, item_num):
    """Return (score, breakdown_dict) for a candidate heading match."""
    breakdown = {}

    if has_exact_item_number(text, match_start):
        breakdown["exact_item"] = WEIGHTS["exact_item"]
    if has_markdown_heading(text, match_start):
        breakdown["markdown_heading"] = WEIGHTS["markdown_heading"]

    # TOC anchors in body text are usually the Table-of-Contents entry itself
    # (NOT the real section), so we treat anchor presence as a NEGATIVE for
    # body detection. If real anchor-ID -> position mapping is built later,
    # this can become a positive signal instead.
    if has_toc_anchor(text, match_start, match_end):
        breakdown["toc_anchor_penalty"] = -WEIGHTS["toc_anchor"]

    if looks_like_heading_line(text, match_start, match_end):
        breakdown["bare_heading_shape"] = WEIGHTS["bare_heading_shape"]
    if has_negative_context(text, match_start, match_end):
        breakdown["negative_context"] = WEIGHTS["negative_context"]
    if has_length_support(text, match_end, next_boundary, doc_length, item_num):
        breakdown["length_support"] = WEIGHTS["length_support"]

    return sum(breakdown.values()), breakdown

def find_next_boundary(text, search_from, current_item, doc_length):
    best = len(text)
    for other_num, other_kw in ITEM_KEYWORDS.items():
        if other_num == current_item:
            continue
        for m in re.finditer(other_kw, text[search_from:], re.IGNORECASE):
            abs_start = search_from + m.start()
            abs_end = search_from + m.end()
            if has_toc_anchor(text, abs_start, abs_end):
                continue
            if has_negative_context(text, abs_start, abs_end):
                continue
            if not looks_like_heading_line(text, abs_start, abs_end):
                continue
            if abs_start < best:
                best = abs_start
            break
    return best

def split_into_sections_v3(raw_text: str, return_scores: bool = False):
    text = normalize_table_noise(raw_text)
    doc_length = len(text)
    results = {}
    score_log = {}

    for item_num, kw in ITEM_KEYWORDS.items():
        candidates = list(re.finditer(kw, text, re.IGNORECASE))
        best_choice = None
        best_score = 0.5  # must clear the low threshold to be accepted

        for m in candidates:
            next_boundary = find_next_boundary(text, m.end(), item_num, doc_length)
            score, breakdown = score_candidate(text, m.start(), m.end(),
                                                next_boundary, doc_length, item_num)
            if score >= best_score:
                best_score = score
                best_choice = (m.start(), next_boundary, score, breakdown)

        if best_choice:
            start, end, score, breakdown = best_choice
            results[item_num] = text[start:end]
            score_log[item_num] = {"score": score, "breakdown": breakdown,
                                   "confident": score >= HIGH_THRESHOLD}

    if return_scores:
        return results, score_log
    return results



