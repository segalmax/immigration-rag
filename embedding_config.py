"""
Titan embedding JSON shape and OpenSearch vector field metadata.
Embedding dimension is loaded once from live GET /_mapping (single runtime source of truth).
"""
import json

import requests

OPENSEARCH_VECTOR_FIELD = "vector"
TITAN_EMBED_NORMALIZE = True
EXPECTED_KNN_SPACE_TYPE = "innerproduct"

_cached_dimension: int | None = None


def _vector_field_props_from_mapping(mapping_response: dict) -> dict:
    for _name, idx_body in mapping_response.items():
        props = idx_body.get("mappings", {}).get("properties", {})
        if OPENSEARCH_VECTOR_FIELD in props:
            return props[OPENSEARCH_VECTOR_FIELD]
    raise KeyError(f"No field {OPENSEARCH_VECTOR_FIELD!r} in GET _mapping response")


def load_opensearch_vector_spec(os_endpoint: str, os_index: str, auth) -> None:
    """GET live index mapping; cache vector dimension; validate knn_vector + innerproduct. Idempotent."""
    global _cached_dimension
    if _cached_dimension is not None:
        return
    url = f"{os_endpoint.rstrip('/')}/{os_index}/_mapping"
    response = requests.get(url, auth=auth, timeout=30)
    response.raise_for_status()
    data = response.json()
    v = _vector_field_props_from_mapping(data)
    if v.get("type") != "knn_vector":
        raise ValueError(f"Expected type knn_vector for {OPENSEARCH_VECTOR_FIELD!r}, got {v.get('type')!r}")
    dim = v.get("dimension")
    if dim is None:
        raise ValueError(f"OpenSearch mapping has no dimension for {OPENSEARCH_VECTOR_FIELD!r}")
    st = (v.get("method") or {}).get("space_type")
    if st != EXPECTED_KNN_SPACE_TYPE:
        raise ValueError(f"OpenSearch space_type {st!r} != expected {EXPECTED_KNN_SPACE_TYPE!r}")
    _cached_dimension = int(dim)


def embedding_dimension() -> int:
    if _cached_dimension is None:
        raise RuntimeError("load_opensearch_vector_spec must run before embedding_dimension()")
    return _cached_dimension


def titan_embed_invoke_body_json(text: str) -> str:
    if _cached_dimension is None:
        raise RuntimeError("load_opensearch_vector_spec must run before titan_embed_invoke_body_json()")
    return json.dumps({
        "inputText": text,
        "dimensions": _cached_dimension,
        "normalize": TITAN_EMBED_NORMALIZE,
    })
