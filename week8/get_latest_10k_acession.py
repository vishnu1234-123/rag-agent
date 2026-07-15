import requests

HEADERS={"User-Agent":"vishnu vishnuvardhan1920@gmail.com"}

def get_latest_10k_accession(cik:str)->tuple[str,str]:
    cik_padded=cik.zfill(0)
    url=f"https://data.sec.gov/submissions/CIK{cik_padded}.json"
    resp=requests.get(url,headers=HEADERS)
    resp.raise_for_status()
    data=resp.json()

    recent=data["filings"]["recent"]
    forms=recent["form"]
    accessions=recent["accessionNumber"]
    dates=recent["filingDate"]

    for i,form in enumerate(forms):
        if form=="10-K":
            return accessions[i],dates[i]
    return None,None