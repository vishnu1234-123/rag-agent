import json, glob, re

# Prose chunks = has_table False. Check for the corruption patterns
# that would indicate the same rendering disease leaked into narrative.
tripled_phrase = 0
sample_bad = []
checked = 0

for f in glob.glob('data/chunks/*.json'):
    for c in json.load(open(f)):
        if c.get('has_table'):
            continue
        checked += 1
        t = c['text']
        # signature of triplication in prose: same 3+ word phrase
        # repeated back-to-back with no separator
        # e.g. "Risk FactorsRisk FactorsRisk Factors"
        m = re.search(r'([A-Z][a-zA-Z]{4,}(?:\s+[A-Za-z]+){1,3})\1', t)
        if m:
            tripled_phrase += 1
            if len(sample_bad) < 8:
                sample_bad.append((f.split('/')[-1], m.group(0)[:80]))

print(f"prose chunks checked: {checked:,}")
print(f"prose chunks with back-to-back repeated phrases: {tripled_phrase:,}")
print(f"  ({100*tripled_phrase/checked:.1f}% of prose)")
print()
if sample_bad:
    print("=== samples (is this corruption or legitimate repetition?) ===")
    for fn, s in sample_bad:
        print(f"  {fn}: {s!r}")
else:
    print("no repeated-phrase corruption detected in prose")

# second check: does prose read as coherent sentences?
# sample a few chunks and eyeball word/char ratio (corruption inflates it)
print()
print("=== prose sanity: chars per word (normal English ~5-6) ===")
import statistics
ratios = []
for f in sorted(glob.glob('data/chunks/*.json'))[:5]:
    for c in json.load(open(f)):
        if c.get('has_table'):
            continue
        words = c['text'].split()
        if len(words) > 20:
            ratios.append(len(c['text']) / len(words))
if ratios:
    print(f"  median: {statistics.median(ratios):.1f}  (>>6 would signal corruption)")
