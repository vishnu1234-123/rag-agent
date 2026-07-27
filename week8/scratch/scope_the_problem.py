import json, glob, re

# The ACTUAL problem is oversized chunks that make oversized parents.
# Everything else works. So: how many chunks are genuinely too big,
# and what are they?
big = []
for f in glob.glob('data/chunks/*.json'):
    for i, c in enumerate(json.load(open(f))):
        n = len(c['text'])
        if n > 12000:
            real = len(re.sub(r'[|\-\s]', '', c['text']))
            density = real / n
            big.append((n, density, c.get('has_table'), f.split('/')[-1]))

big.sort(reverse=True)
print(f"chunks over 12k chars: {len(big)} (out of 13,961)\n")
print(f"{'chars':>9} {'density':>8} {'table':>6}  file")
for n, d, tbl, fn in big[:25]:
    print(f"{n:>9,} {d*100:>7.1f}% {str(tbl):>6}  {fn}")

# how bad is the tail?
print(f"\nover 12k: {len(big)}")
print(f"over 30k: {sum(1 for b in big if b[0] > 30000)}")
print(f"over 50k: {sum(1 for b in big if b[0] > 50000)}")
print(f"over 100k: {sum(1 for b in big if b[0] > 100000)}")
