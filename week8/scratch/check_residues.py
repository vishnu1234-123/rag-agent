import json, glob, re

suspicious = []
for f in sorted(glob.glob('data/chunks/*.json')):
    for c in json.load(open(f)):
        if not c.get('has_table'):
            continue
        s = re.sub(r'[|\-\s]', '', c['text'])
        if 0 < len(s) < 25:
            # a comma-grouped number or a decimal = plausible financial figure
            if re.search(r'\d{1,3},\d{3}|\d+\.\d{2}|\$', s):
                suspicious.append((f.split('/')[-1], c['text'][:100]))

print(f'residues containing figure-like content: {len(suspicious)}')
for name, t in suspicious[:10]:
    print(f'  {name:<18} {t!r}')
