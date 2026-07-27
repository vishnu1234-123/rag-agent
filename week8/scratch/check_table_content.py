import json, glob, re

# Of the has_table chunks, how many are pure numeric tables (safe to drop)
# vs. mostly prose with a small table (maybe keep)?
pure_table = mostly_prose = 0
prose_samples = []
for f in glob.glob('data/chunks/*.json'):
    for c in json.load(open(f)):
        if not c.get('has_table'):
            continue
        t = c['text']
        # fraction of lines that are table rows (pipe-delimited)
        lines = [l for l in t.splitlines() if l.strip()]
        if not lines:
            continue
        table_lines = sum(1 for l in lines if l.strip().startswith('|'))
        table_frac = table_lines / len(lines)
        if table_frac > 0.7:
            pure_table += 1
        else:
            mostly_prose += 1
            if len(prose_samples) < 5:
                # the prose part, stripped of table lines
                prose = ' '.join(l for l in lines if not l.strip().startswith('|'))
                prose_samples.append((f.split('/')[-1], prose[:200]))

print(f"pure tables (>70% pipe rows) — safe to drop: {pure_table:,}")
print(f"mostly prose with small table — review:      {mostly_prose:,}")
print()
for fn, s in prose_samples:
    print(f"{fn}: {s!r}\n")
