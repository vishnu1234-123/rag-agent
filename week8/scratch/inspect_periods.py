from xbrl_companyfacts import fetch_by_ticker, get_concept_values
from datetime import date

facts = fetch_by_ticker("AAPL")
vals = get_concept_values(facts, "net_income")
# look at the 2020 entries specifically
for v in vals:
    if v.get("end","").startswith("2020"):
        start, end = v.get("start"), v.get("end")
        days = None
        if start and end:
            try: days = (date.fromisoformat(end)-date.fromisoformat(start)).days
            except: pass
        print(f"end={end} start={start} days={days} val={v['val']/1e9:.1f}B fp={v.get('fp')} fy={v.get('fy')} frame={v.get('frame')}")
