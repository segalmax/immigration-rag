"""
scripts/create_index.py
One-time script to create the OpenSearch k-NN index with the correct mapping.
Run once before indexing any documents.

Usage:
    python scripts/create_index.py

TODO: set VECTOR_DIM to match your Titan Embeddings model output dimension (1536 for v1).
"""
import os
from dotenv import load_dotenv
load_dotenv()

from opensearch_utils import _get_client

OS_INDEX   = os.getenv("OS_INDEX", "uscis-policy")
VECTOR_DIM = 1536   # Titan Embeddings v1


def create_index() -> None:
    client = _get_client()

    if client.indices.exists(index=OS_INDEX):
        print(f"Index '{OS_INDEX}' already exists — skipping.")
        return

    mapping = {
        "settings": {
            "index": {
                "knn": True,
                "knn.algo_param.ef_search": 100,
            }
        },
        "mappings": {
            "properties": {
                "vector": {
                    "type": "knn_vector",
                    "dimension": VECTOR_DIM,
                    "method": {
                        "name": "hnsw",
                        "space_type": "cosinesimil",
                        "engine": "nmslib",
                    },
                },
                "text":    {"type": "text"},
                "source":  {"type": "keyword"},
                "section": {"type": "keyword"},
            }
        },
    }

    client.indices.create(index=OS_INDEX, body=mapping)
    print(f"Index '{OS_INDEX}' created with dim={VECTOR_DIM}.")


if __name__ == "__main__":
    create_index()
