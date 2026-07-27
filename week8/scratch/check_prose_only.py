import json, glob
from collections import defaultdict

prose_by_section = defaultdict(int)
table_by_section = defaultdict(int)
prose_total = table_total = 0

for f in glob.glob('data/chunks/*.json'):
    for c in json.load(open(f)):
        sec = c.get('section_item') or 'NONE'
        if c.get('has_table'):
            table_by_section[sec] += 1
            table_total += 1
        else:
            prose_by_section[sec] += 1
            prose_total += 1

print(f"prose chunks kept:  {prose_total:,}")
print(f"table chunks dropped: {table_total:,}\n")

# sections that exist ONLY as tables (would vanish entirely)
only_tables = [s for s in table_by_section if prose_by_section[s] == 0]
print(f"sections that become empty after dropping tables: {len(only_tables)}")
for s in only_tables[:15]:
    print(f"  Item {s}: {table_by_section[s]} table chunks, 0 prose")
