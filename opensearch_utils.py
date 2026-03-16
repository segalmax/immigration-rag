"""
opensearch_utils.py — OpenSearch k-NN helpers
Provides:
  index(doc_id, vector, metadata) → None
  search(query_vector, k)         → list[dict]
"""
import os
from opensearchpy import OpenSearch, RequestsHttpConnection
from requests_aws4auth import AWS4Auth
import boto3

OS_HOST   = os.getenv("OS_HOST")
OS_INDEX  = os.getenv("OS_INDEX", "uscis-policy")
AWS_REGION = os.getenv("AWS_REGION", "us-east-1")

_client = None


def _get_client() -> OpenSearch:
    global _client
    if _client is None:
        credentials = boto3.Session().get_credentials()
        awsauth = AWS4Auth(
            credentials.access_key, credentials.secret_key,
            AWS_REGION, "es",
            session_token=credentials.token,
        )
        _client = OpenSearch(
            hosts=[{"host": OS_HOST, "port": 443}],
            http_auth=awsauth,
            use_ssl=True,
            verify_certs=True,
            connection_class=RequestsHttpConnection,
        )
    return _client


def index(doc_id: str, vector: list, metadata: dict) -> None:
    """Index a single chunk with its embedding vector."""
    # TODO: implement
    body = {"vector": vector, **metadata}
    _get_client().index(index=OS_INDEX, id=doc_id, body=body)


def search(query_vector: list, k: int = 5) -> list:
    """Return top-k chunks nearest to query_vector."""
    # TODO: implement
    query = {
        "size": k,
        "query": {
            "knn": {
                "vector": {"vector": query_vector, "k": k}
            }
        }
    }
    resp = _get_client().search(index=OS_INDEX, body=query)
    return [hit["_source"] for hit in resp["hits"]["hits"]]
