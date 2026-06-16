import os
from dotenv import load_dotenv
from pinecone import Pinecone
load_dotenv()

pc=Pinecone(api_key=os.getenv("PINECONE_API_KEY"))

#list existing indexes
indexes=pc.list_indexes()
print(f"Existing indexes:{indexes}")

#connect to your index
index=pc.Index("filingsiq-dev")
stats=index.describe_index_stats()
print(f"\nIndex stats: {stats}")
print(f"Total vectors: {stats['total_vector_count']}")
print(f"Dimension: {stats['dimension']}")