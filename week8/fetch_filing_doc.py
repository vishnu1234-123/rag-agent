import requests
from urllib.parse import urljoin




HEADERS={
    "User-Agent":"vishnu vishnuvardhan1920@gmail.com"
}

def get_filing_index(cik:str,accession_no:str)->str:
    "return the url of filing index directory "
    cik_padded=cik.zfill(0)
    acc_no_dashless=accession_no.replace("-","")
    return f"https://www.sec.gov/Archives/edgar/data/{cik_padded}/{acc_no_dashless}/"

def find_main_filing_doc(index_url:str)->str:
    resp=requests.get(index_url,headers=HEADERS)
    resp.raise_for_status()

    from bs4 import BeautifulSoup
    soup=BeautifulSoup(resp.text,"html.parser")
    filing_path_marker=index_url.replace("https://www.sec.gov","")
    candidates=[]
    for link in soup.find_all("a"):
        href=link.get("href","")
        if not href.startswith(filing_path_marker):
            continue
        if not href.endswith(".htm"):
            continue
        filename=href.split("/")[-1]
        if filename.startswith("R") and filename[1:].split(".")[0].isdigit():
            continue
        if "index" in filename.lower():
            continue
        if filename.startswith("a10-k") or filename.startswith("a10k"):
            continue
        candidates.append(filename)
    if not candidates:
        raise ValueError(f"No main filing doc found at {index_url}")
    import re
    date_pattern=re.compile(r"-\d{8}\.htm$")
    dated=[c for c in candidates if date_pattern.search(c)]
    if dated:
        return dated[0]
    return candidates[0]

def fetch_finding_html(cik:str,acession_no:str)->str:
    index_url=get_filing_index(cik,acession_no)
    filename=find_main_filing_doc(index_url)
    full_url=urljoin(index_url,filename)
    print(f"Fetching main filing doc: {full_url}")
    resp=requests.get(full_url,headers=HEADERS)
    resp.raise_for_status()
    return resp.text
