"""
Week 8 - Embedding & Loading phase configuration.

Single source of truth for every knob in the pipeline.
"""

from pathlib import Path

ROOT=Path(__file__).resolve().parent
DATA=ROOT/"data"

CHUNKS_DIR=DATA/"chunks"      #input : your 13,939 chunks
PARENT_DB=DATA/"parents.sqlite"   # stage 1 output
MANIFEST=DATA/"manifest.json"    #stage 2 checkpoint {id:content_hash}
DEAD_LETTER=DATA/"dead_letter.json"  #stage 2 failures

#---- chunking

CHUNK_OVERLAP_TOKENS=100

#---- parents

CHILDREN_PER_PARENT=3   # ~3200 tokens per parent
PARENT_PER_QUERY=5    # retrieval - time cap (~16k context)

#---- embedding
EMBED_MODEL="text-embedding-3-small"
EMBED_DIM=1536
EMBED_BATCH_SIZE=100

#---- pinecone

INDEX_NAME="filingsiq"
INDEX_METRIC="dotproduct"   #irreversible after index creation
INDEX_CLOUD="aws"
INDEX_REGION="us-east-1"
NAMESPACE="v1"

#---- expectations

EXPECTED_CHUNKS=6779



