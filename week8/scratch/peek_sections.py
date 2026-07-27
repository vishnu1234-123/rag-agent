"""
Sanity-peek at section boundaries, with self-diagnostics so 'file missing'
tells us WHY (wrong path vs genuinely absent).
"""
from pathlib import Path
from section_splitter import split_into_sections

PROCESSED = Path("data/processed")

for ticker in ["AAPL", "JPM", "XOM"]:
    tdir = PROCESSED / ticker
    print(f"\n{'='*60}\n{ticker}\n{'='*60}")

    if not tdir.exists():
        print(f"  folder {tdir} does NOT exist")
        if PROCESSED.exists():
            print(f"  available folders: {sorted(p.name for p in PROCESSED.iterdir() if p.is_dir())}")
        continue

    files = sorted(p.name for p in tdir.iterdir())
    print(f"  files present: {files}")

    path = tdir / f"{ticker}_10K_full.md"
    if not path.exists():
        print(f"  expected file {path.name} NOT found - check naming above")
        continue

    sections = split_into_sections(path.read_text())
    print(f"  {len(sections)} sections:")
    for s in sections:
        item = s['item'] or '(none)'
        title = (s['title'] or '')[:45]
        print(f"    Item {item:<5} {len(s['text']):>8,} chars  {title}")