"""
Bedrock Runtime (Titan + Claude), Titan/OpenSearch vector spec from live _mapping, and RAG /ask orchestration.
"""
import json
import os

import boto3
import requests
import src.opensearch_utils

REGION = os.environ["AWS_REGION"]
TITAN_EMBED_MODEL = os.environ["TITAN_EMBED_MODEL"]
CLAUDE_MODEL_ID = os.environ["CLAUDE_MODEL_ID"]

OS_ENDPOINT = f"https://{os.environ['OS_HOST']}"
OS_INDEX = os.environ["OS_INDEX"]

KNN_TOP_K = 5

OPENSEARCH_VECTOR_FIELD = "vector"
TITAN_EMBED_NORMALIZE = True
EXPECTED_KNN_SPACE_TYPE = "innerproduct"

_cached_dimension: int | None = None

BEDROCK_RUNTIME = boto3.client("bedrock-runtime", region_name=REGION)


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


def ensure_opensearch_vector_spec_loaded() -> None:
    load_opensearch_vector_spec(OS_ENDPOINT, OS_INDEX, src.opensearch_utils.OPENSEARCH_HTTP_AUTH)


def embed_text_for_titan(text: str) -> list:
    ensure_opensearch_vector_spec_loaded()
    body = titan_embed_invoke_body_json(text)
    response = BEDROCK_RUNTIME.invoke_model(
        body=body,
        modelId=TITAN_EMBED_MODEL,
        contentType="application/json",
        accept="application/json",
    )
    return json.loads(response["body"].read())["embedding"]


def invoke_claude(body: str, model_id: str | None = None) -> dict:
    mid = model_id or CLAUDE_MODEL_ID
    response = BEDROCK_RUNTIME.invoke_model(
        body=body,
        modelId=mid,
        contentType="application/json",
        accept="application/json",
    )
    return json.loads(response["body"].read())


def knn_search_top_chunks(query_vector: list, k: int, category_filter: str | None = None) -> list[dict]:
    ensure_opensearch_vector_spec_loaded()
    return src.opensearch_utils.knn_search_top_chunks(
        OS_ENDPOINT, OS_INDEX, query_vector, k, category_filter=category_filter
    )


def answer_question_with_claude(question: str, chunks: list[dict]) -> str:
    lines = []
    for i, ch in enumerate(chunks, 1):
        meta = f"s3_key={ch.get('s3_key')!r} section_path={ch.get('section_path')!r} source_url={ch.get('source_url')!r}"
        lines.append(f"--- CONTEXT {i} ({meta}) ---\n{ch.get('text', '')}")
    context_block = "\n\n".join(lines)
    user_block = f"CONTEXT (use only this to answer):\n\n{context_block}\n\nQUESTION:\n{question}"
    body = json.dumps({
        "anthropic_version": "bedrock-2023-05-31",
        "max_tokens": 4096,
        "system": (
            "You answer using ONLY the CONTEXT blocks above. If the context is insufficient, say so clearly. "
            "Cite which context block (by number) supports each claim. Do not invent USCIS facts. "
            "If the question cannot be answered with high confidence using the context, refuse to answer and say so clearly. "
            "NEVER use your own knowledge to answer the question!"
        ),
        "messages": [{"role": "user", "content": user_block}],
    })
    out = invoke_claude(body)
    parts = out.get("content") or []
    if not parts:
        raise ValueError(f"Claude response missing content: {out!r}")
    return parts[0].get("text", "")


def run_ask(question: str) -> tuple[str, list[dict]]:
    """Returns (answer_markdown, sources_for_json)."""
    vec = embed_text_for_titan(question)
    chunks = knn_search_top_chunks(vec, KNN_TOP_K)
    if not chunks:
        raise LookupError("No chunks returned from OpenSearch for this query")
    answer = answer_question_with_claude(question, chunks)
    sources = []
    for ch in chunks:
        sources.append({
            "s3_key": ch.get("s3_key"),
            "source_url": ch.get("source_url"),
            "section_path": ch.get("section_path"),
            "volume": ch.get("volume"),
            "part": ch.get("part"),
            "chapter": ch.get("chapter"),
            "snippet": (ch.get("text") or "")[:400],
            "score": ch.get("score"),
        })
    return answer, sources
