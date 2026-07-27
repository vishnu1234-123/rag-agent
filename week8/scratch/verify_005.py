import json, glob, re

filtered = []
for f in glob.glob('data/chunks/*.json'):
    for c in json.load(open(f)):
        if not c.get('has_table'):
            continue
        t = c['text']
        if len(t) < 5000:
            continue
        real = re.sub(r'[|\-\s]', '', t)
        d = len(real) / len(t)
        if d < 0.05:
            filtered.append((d*100, len(t), len(real), real[:250], f.split('/')[-1]))

filtered.sort()
print(f'{len(filtered)} chunks below 5% density\n')
print('=== LOWEST density (expect pure layout artifact) ===')
for d, tot, real, s, fn in filtered[:4]:
    print(f'{d:.1f}%  {real} real chars  {fn}')
    print(f'   {s!r}\n')
print('=== HIGHEST density within the band (the risky edge) ===')
for d, tot, real, s, fn in filtered[-6:]:
    print(f'{d:.1f}%  {real} real chars  {fn}')
    print(f'   {s!r}\n')
