
"""

Regenerate ONE filing's markdown with deduped tables, compare to the old.

Proves the fix works before committing to all 40.

Re-runs Docling on one file (~1 min).

"""

from pathlib import Path

from docling.document_converter import DocumentConverter

from docling_core.types.doc import TableItem, TextItem

from dedup_columns import dedup_triplicated_columns

RAW = Path("/Users/vishnuvardhan/Desktop/RAG AGENT/data/raw/XOM")

raw_files = list(RAW.glob("*"))

if not raw_files:

    print(f"no raw file in {RAW}"); raise SystemExit

raw_path = raw_files[0]

print(f"parsing {raw_path.name} (one-time Docling run)...")

doc = DocumentConverter().convert(str(raw_path)).document

# OLD way - raw markdown, triplicated

old_md = doc.export_to_markdown()

# NEW way - walk in reading order, dedup each table

parts = []

tables_seen = tables_deduped = 0

for item, _level in doc.iterate_items():

    if isinstance(item, TableItem):

        tables_seen += 1

        try:

            df = item.export_to_dataframe(doc)

        except TypeError:

            df = item.export_to_dataframe()

        before_cols = df.shape[1]

        df = dedup_triplicated_columns(df)

        if df.shape[1] < before_cols:

            tables_deduped += 1

        parts.append(df.to_markdown(index=False))

    elif isinstance(item, TextItem):

        parts.append(item.text)

new_md = "\n\n".join(parts)

print(f"\ntables: {tables_seen} seen, {tables_deduped} had columns collapsed")

print(f"old markdown: {len(old_md):,} chars")

print(f"new markdown: {len(new_md):,} chars")

print(f"reduction   : {100*(1-len(new_md)/len(old_md)):.1f}%")

# did the 107k signature-page monster shrink?

old_max_line = max(len(l) for l in old_md.splitlines())

new_max_line = max(len(l) for l in new_md.splitlines())

print(f"\nlongest single line - old: {old_max_line:,}  new: {new_max_line:,}")

# find biggest table block in each

def biggest_table_block(md):

    blocks, cur = [], []

    for line in md.splitlines():

        if line.strip().startswith("|"):

            cur.append(line)

        else:

            if cur: blocks.append(sum(len(l) for l in cur)); cur = []

    if cur: blocks.append(sum(len(l) for l in cur))

    return max(blocks) if blocks else 0

print(f"biggest table block  - old: {biggest_table_block(old_md):,}  new: {biggest_table_block(new_md):,}")

