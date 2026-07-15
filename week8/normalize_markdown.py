import re

def normalize_table_noise(text:str)->str:

    text=re.sub(r"\|"," ",text)
    text=re.sub(r"[ \t]{2,}"," ",text)

    text=re.sub(r"\b(.{3,40}?)(\s*\1){1,}", r"\1",text,flags=re.IGNORECASE)
    return text

