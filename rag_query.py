"""
RAG query path: Titan query embed, OpenSearch k-NN, Claude grounded answer.
"""
import json
import os

import boto3
import embedding_config
import requests
import requests_aws4auth

REGION = os.environ["AWS_REGION"]
OS_ENDPOINT = f"https://{os.environ['OS_HOST']}"
OS_INDEX = os.environ["OS_INDEX"]
TITAN_MODEL = os.environ["TITAN_EMBED_MODEL"]
CLAUDE_MODEL = os.environ["CLAUDE_MODEL_ID"]

KNN_TOP_K = 5

_bedrock = None
_os_auth = None
def bedrock_runtime():
    global _bedrock
    if _bedrock is None:
        _bedrock = boto3.client("bedrock-runtime", region_name=REGION)
    return _bedrock


def opensearch_http_auth():
    global _os_auth
    if _os_auth is None:
        creds = boto3.Session().get_credentials().get_frozen_credentials()
        _os_auth = requests_aws4auth.AWS4Auth(
            creds.access_key,
            creds.secret_key,
            REGION,
            "aoss",
            session_token=creds.token,
        )
    return _os_auth


def ensure_opensearch_vector_spec_loaded() -> None:
    embedding_config.load_opensearch_vector_spec(OS_ENDPOINT, OS_INDEX, opensearch_http_auth())


def embed_text_for_titan(text: str) -> list:
    ensure_opensearch_vector_spec_loaded()
    body = embedding_config.titan_embed_invoke_body_json(text)
    response = bedrock_runtime().invoke_model(
        body=body,
        modelId=TITAN_MODEL,
        contentType="application/json",
        accept="application/json",
    )
    return json.loads(response["body"].read())["embedding"]


def knn_search_top_chunks(query_vector: list, k: int) -> list[dict]:
    ensure_opensearch_vector_spec_loaded()
    vf = embedding_config.OPENSEARCH_VECTOR_FIELD
    payload = {
        "size": k,
        "query": {
            "knn": {
                vf: {
                    "vector": query_vector,
                    "k": k,
                }
            }
        },
    }
    url = f"{OS_ENDPOINT}/{OS_INDEX}/_search"
    response = requests.post(
        url,
        auth=opensearch_http_auth(),
        json=payload,
        headers={"Content-Type": "application/json"},
        timeout=60,
    )
    response.raise_for_status()
    data = response.json()
    hits = data.get("hits", {}).get("hits", [])
    out = []
    for h in hits:
        src = h.get("_source", {})
        out.append({
            "s3_key": src.get("s3_key"),
            "category": src.get("category"),
            "volume": src.get("volume"),
            "part": src.get("part"),
            "chapter": src.get("chapter"),
            "source_url": src.get("source_url"),
            "section_path": src.get("section_path"),
            "text": src.get("text"),
            "score": h.get("_score"),
        })
    return out


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
            "Cite which context block (by number) supports each claim. Do not invent USCIS facts."
        ),
        "messages": [{"role": "user", "content": user_block}],
    })
    response = bedrock_runtime().invoke_model(
        body=body,
        modelId=CLAUDE_MODEL,
        contentType="application/json",
        accept="application/json",
    )
    out = json.loads(response["body"].read())
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
