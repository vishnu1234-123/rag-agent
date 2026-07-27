import json, glob, re, collections

# For each table row, find runs of identical adjacent cells and record
# the run length. This tells us if it's uniformly 3x, mixed, 2x, etc.
run_lengths = collections.Counter()
mixed_rows = 0
clean_rows = 0
sample_mixed = []

for f in glob.glob('data/chunks/*.json'):
    for c in json.load(open(f)):
        if not c.get('has_table'):
            continue
        for line in c['text'].splitlines():
            if not line.strip().startswith('|'):
                continue
            cells = [x.strip() for x in line.strip().strip('|').split('|')]
            cells = [x for x in cells if x and not set(x) <= set('- ')]
            if len(cells) < 2:
                continue
            # compute run lengths
            runs = []
            prev, n = None, 0
            for cell in cells:
                if cell == prev:
                    n += 1
                else:
                    if prev is not None:
                        runs.append(n)
                    prev, n = cell, 1
            if prev is not None:
                runs.append(n)

            distinct = set(runs)
            if distinct == {1}:
                clean_rows += 1
            elif len(distinct) == 1:
                run_lengths[f'uniform {distinct.pop()}x'] += 1
            else:
                mixed_rows += 1
                # record the actual run pattern for mixed rows
                if len(sample_mixed) < 8:
                    sample_mixed.append((f.split('/')[-1], runs, cells[:6]))

print("=== table row repetition patterns ===")
print(f"clean (no adjacent repeats, all 1x): {clean_rows:,}")
for pat, n in sorted(run_lengths.items()):
    print(f"{pat:<16}: {n:,}")
print(f"MIXED run-lengths (e.g. [3,2] or [3,1]): {mixed_rows:,}")
print()
print("=== sample mixed rows (the inconsistent ones you asked about) ===")
for fn, runs, cells in sample_mixed:
    print(f"{fn}  runs={runs}")
    print(f"   {cells}")
