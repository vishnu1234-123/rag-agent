import json, glob, re, collections

lengths, texts = [], collections.Counter()
for f in sorted(glob.glob('data/chunks/*.json')):
    for c in json.load(open(f)):
        if not c.get('has_table'):
            continue
        s = re.sub(r'[|\-\s]', '', c['text'])
        lengths.append(len(s))
        texts[c['text']] += 1

total = len(lengths)
print(f'table chunks: {total}\n')

print('=== stripped-length distribution ===')
bands = [(0,25),(25,50),(50,100),(100,250),(250,1000),(1000,10**9)]
for lo, hi in bands:
    n = sum(1 for L in lengths if lo <= L < hi)
    label = f'{lo}-{hi}' if hi < 10**9 else f'{lo}+'
    print(f'  {label:<10} {n:>6}  {100*n/total:>5.1f}%  {"#"*int(60*n/total)}')

print('\n=== just above the threshold (25-60 chars) ===')
seen = 0
for f in sorted(glob.glob('data/chunks/*.json')):
    name = f.split('/')[-1]
    for c in json.load(open(f)):
        if not c.get('has_table'):
            continue
        s = re.sub(r'[|\-\s]', '', c['text'])
        if 25 <= len(s) < 60:
            print(f'  {name:<16} {len(s):>3}  {s[:70]!r}')
            seen += 1
            if seen >= 12:
                break
    if seen >= 12:
        break

print('\n=== exact duplicates ABOVE the threshold ===')
dupes = [(t, n) for t, n in texts.items()
         if n > 1 and len(re.sub(r'[|\-\s]', '', t)) >= 25]
print(f'  {len(dupes)} distinct texts appear more than once')
print(f'  {sum(n for _, n in dupes)} chunks involved')
for t, n in sorted(dupes, key=lambda x: -x[1])[:8]:
    print(f'    {n:>4}x  {re.sub(chr(10)," ",t)[:75]!r}')
