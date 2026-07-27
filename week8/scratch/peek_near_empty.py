import json, glob, re, collections

residues = collections.Counter()
per_file = collections.Counter()

for f in sorted(glob.glob('data/chunks/*.json')):
    name = f.split('/')[-1]
    for c in json.load(open(f)):
        if not c.get('has_table'):
            continue
        s = re.sub(r'[|\-\s]', '', c['text'])
        if 0 < len(s) < 25:
            residues[s] += 1
            per_file[name] += 1

print("=== what actually survives stripping ===")
for text, n in residues.most_common(20):
    print(f'  {n:>4}x  {text!r}')
print(f'\n  ...{len(residues)} distinct residues total')

print("\n=== per file ===")
for name, n in per_file.most_common(12):
    print(f'  {name:<20} {n}')
