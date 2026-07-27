"""
FilingsIQ - Section boundary detection for structure-aware chunking
(Week 8, Step 12 - chunking foundation)

Structure-aware chunking needs reliable section boundaries. Our survey
showed 'Item N.' detection is messy: clean for most filers, MERGED onto
one line for JPM/BAC ('Item 6. Reserved Item 7. MD&A...'), and effectively
ABSENT from the body for XOM/AMZN/WMT (only in ToC).

This module splits a filing's markdown into sections, handling all three
cases, and CRUCIALLY guarantees no content loss: every character of the
document lands in exactly one section. Where headers can't be detected,
content folds into the current section rather than being dropped - a
missing boundary degrades to a bigger section, never to lost text.

Returns a list of sections: {item, title, start_line, text}. The 'item'
is None where no boundary was detectable (content still preserved).

USAGE (as a module):
    from section_splitter import split_into_sections
    sections = split_into_sections(markdown_text)
"""

import re

def _is_strucutral_line(line:str)->bool:
    s=line.strip()
    if "](#" in s:
        return False
    if s.startswith("|"):
        return False
    return True

def split_into_sections(markdown_text:str)->list[dict]:
    lines=markdown_text.splitlines()
    boundaries=[]

    for i,line in enumerate(lines):
        if not _is_strucutral_line(line):
            continue
        m=re.match(r"\s*Item\s+(\d+[A-Z]?)\.\s+([A-Z].*)", line, re.IGNORECASE)
        if m:
            item_num=m.group(1).upper()
            title=m.group(2).strip()[:80]
            boundaries.append((i,item_num,title))

    if not boundaries:
        return [{"item":None,"title":None,"start_line":0,"text":markdown_text}]
    sections=[]

    if boundaries[0][0]>0:
        preamble="\n".join(lines[:boundaries[0][0]])
        if preamble.strip():
            sections.append({"item":None,"title":"preamble","start_line":0,"text":preamble})
    
    for b_idx,(line_idx,item_num,title) in enumerate(boundaries):
        end=boundaries[b_idx+1][0] if b_idx+1<len(boundaries) else len(lines)
        text="\n".join(lines[line_idx:end])
        sections.append({"item":item_num,"title":title,"start_line":line_idx,"text":text})
    return sections

def verify_no_loss(markdown_text:str,sections=list[dict])->bool:
    original=re.sub(r"\s+","",markdown_text)
    rebuilt= re.sub(r"\s+","","".join(s["text"] for s in sections))
    return original==rebuilt

if __name__=="__main__":
    clean = """Item 1. Business
We design and sell devices.
Item 1A. Risk Factors
Our business faces risks.
Item 7. MD&A
Revenue grew this year."""
    s=split_into_sections(clean)
    print(f"Clean case: {len(s)} sections,items={[x['item'] for x in s]}")
    assert [x['item'] for x in s]==['1','1A','7'],"clean case failed"
    assert verify_no_loss(clean,s),"clean case LOST CONTENT"

    noheaders="""We are a global energy company.
Our operations span many countries.
Cybersecurity is a key concern."""

    s2=split_into_sections(noheaders)
    print(f"No-header case: {len(s2)} section(s), items={[x['item'] for x in s2]}")
    assert len(s2)==1 and s2[0]['item'] is None,"no-header case failed"
    assert verify_no_loss(noheaders,s2)

    preamble= """UNITED STATES SECURITIES AND EXCHANGE COMMISSION
Form 10-K
Item 1. Business
We make things."""
    s3=split_into_sections(preamble)
    print(f"Preamble case: {len(s3)} sections, items={[x['item'] for x in s3]}")
    assert verify_no_loss(preamble, s3), "preamble case LOST CONTENT"

    print("\nAll section-splitter self-tests passed (no content loss in any case).")
                    


