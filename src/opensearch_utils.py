"""OpenSearch Serverless HTTP (SigV4) and k-NN search."""
import os

import boto3
import requests
import requests_aws4auth

REGION = os.environ["AWS_REGION"]
_CREDS = boto3.Session().get_credentials().get_frozen_credentials()
OPENSEARCH_HTTP_AUTH = requests_aws4auth.AWS4Auth(
    _CREDS.access_key,
    _CREDS.secret_key,
    REGION,
    "aoss",
    session_token=_CREDS.token,
)


def send_doc_to_opensearch(endpoint: str, index_name: str, doc: dict, auth=None, doc_id: str | None = None) -> None:
    auth = auth or OPENSEARCH_HTTP_AUTH
    base = f"{endpoint.rstrip('/')}/{index_name}/_doc"
    url = f"{base}/{doc_id}" if doc_id else base
    response = (requests.put if doc_id else requests.post)(
        url,
        auth=auth,
        json=doc,
        headers={"Content-Type": "application/json"},
        timeout=30,
    )
    response.raise_for_status()


def knn_search_top_chunks(
    endpoint: str,
    index_name: str,
    query_vector: list,
    k: int,
    category_filter: str | None = None,
) -> list[dict]:
    import src.bedrock_utils
    vf = src.bedrock_utils.OPENSEARCH_VECTOR_FIELD
    knn_leaf = {vf: {"vector": query_vector, "k": k}}
    if category_filter is None:
        payload = {"size": k, "query": {"knn": knn_leaf}}
    else:
        payload = {
            "size": k,
            "query": {
                "bool": {
                    "must": [{"knn": knn_leaf}],
                    "filter": [{"term": {"category": category_filter}}],
                }
            },
        }
    url = f"{endpoint.rstrip('/')}/{index_name}/_search"
    response = requests.post(
        url,
        auth=OPENSEARCH_HTTP_AUTH,
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
