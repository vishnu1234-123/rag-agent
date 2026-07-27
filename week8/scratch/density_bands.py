import json, glob, re

bands = {'<5%':0,'5-15%':0,'15-25%':0,'25-40%':0,'40-60%':0,'60%+':0}
samples = {'5-15%':[], '15-25%':[], '25-40%':[]}

for f in glob.glob('data/chunks/*.json'):
    for c in json.load(open(f)):
        if not c.get('has_table'):
            continue
        t = c['text']
        if len(t) < 5000:
            continue
        real = re.sub(r'[|\-\s]', '', t)
        d = len(real) / len(t) * 100
        if d < 5:
            bands['<5%'] += 1
        elif d < 15:
            bands['5-15%'] += 1
            if len(samples['5-15%']) < 3:
                samples['5-15%'].append((f.split('/')[-1], real[:200]))
        elif d < 25:
            bands['15-25%'] += 1
            if len(samples['15-25%']) < 3:
                samples['15-25%'].append((f.split('/')[-1], real[:200]))
        elif d < 40:
            bands['25-40%'] += 1
            if len(samples['25-40%']) < 3:
                samples['25-40%'].append((f.split('/')[-1], real[:200]))
        elif d < 60:
            bands['40-60%'] += 1
        else:
            bands['60%+'] += 1

print('density distribution of large (>5k char) table chunks:')
for k, v in bands.items():
    print(f'  {k:<8} {v:>5}')
print()
for band, items in samples.items():
    print(f'=== {band} samples ===')
    for fn, s in items:
        print(f'  {fn}: {s!r}')
    print()
