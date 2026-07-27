from pathlib import Path
from docling.document_converter import DocumentConverter
from docling_core.types.doc import TableItem
from dedup_columns import dedup_triplicated_columns

RAW = Path("/Users/vishnuvardhan/Desktop/RAG AGENT/data/raw/XOM")
raw_path = list(RAW.glob("*"))[0]
doc = DocumentConverter().convert(str(raw_path)).document

# find the biggest table and show all three renderings
biggest = None
for item, _ in doc.iterate_items():
    if isinstance(item, TableItem):
        try:
            df = item.export_to_dataframe(doc)
        except TypeError:
            df = item.export_to_dataframe()
        size = df.shape[0] * df.shape[1]
        if biggest is None or size > biggest[0]:
            biggest = (size, item, df)

_, item, df = biggest
print(f"biggest table shape: {df.shape}")
print(f"  docling markdown : {len(item.export_to_markdown(doc)):,} chars")
print(f"  pandas markdown  : {len(df.to_markdown(index=False)):,} chars")
deduped = dedup_triplicated_columns(df)
print(f"  after col-dedup  : {deduped.shape}  ({len(deduped.to_markdown(index=False)):,} chars pandas)")
print()
print("=== first 3 rows, raw cell values (see the triplication) ===")
for i in range(min(3, df.shape[0])):
    print(f"row {i}: {list(df.iloc[i])[:8]}")
print()
print("=== docling's own markdown, first 400 chars ===")
print(item.export_to_markdown(doc)[:400])
