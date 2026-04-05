"""
scripts/create_index.py
One-time setup: create the k-NN index in OpenSearch Serverless.
Mapping and settings are loaded from opensearch/data/opensearch_config_immig-col3.json
(single source of truth shared with opensearch_export.py).

Usage:
    python scripts/create_index.py
"""
import json
import os
import pathlib
import dotenv
import boto3
import requests
import requests_aws4auth

dotenv.load_dotenv()

OS_INDEX    = os.environ["OS_INDEX"]
REGION      = os.environ["AWS_REGION"]

CONFIG_FILE = pathlib.Path(__file__).parent.parent / "opensearch" / "index_schema.json"


def _auth() -> requests_aws4auth.AWS4Auth:
    creds = boto3.Session().get_credentials().get_frozen_credentials()
    return requests_aws4auth.AWS4Auth(creds.access_key, creds.secret_key, REGION, "aoss", session_token=creds.token)


def _collection_name(config: dict) -> str:
    collection = config["collection"]
    return collection["name"]


def _resolve_endpoint(col_name: str) -> str:
    client = boto3.client("opensearchserverless", region_name=REGION)
    details = client.batch_get_collection(names=[col_name])["collectionDetails"]
    assert details, f"Collection '{col_name}' not found in AWS"
    detail = details[0]
    assert detail["status"] == "ACTIVE", f"Collection '{col_name}' is not ACTIVE: {detail['status']}"
    endpoint = detail["collectionEndpoint"]
    env_host = os.environ.get("OS_HOST")
    if env_host and endpoint != f"https://{env_host}":
        print(f"Ignoring stale OS_HOST='{env_host}' and using live endpoint '{endpoint}'.")
    return endpoint


def create_index() -> None:
    config = json.loads(CONFIG_FILE.read_text())
    col_name = _collection_name(config)
    os_endpoint = _resolve_endpoint(col_name)
    resp = requests.put(
        f"{os_endpoint}/{OS_INDEX}",
        auth=_auth(),
        json={"mappings": config["mapping"], "settings": {"index": config["settings"]}},
        headers={"Content-Type": "application/json"},
        timeout=30,
    )
    if resp.status_code == 400 and "resource_already_exists_exception" in resp.text:
        print(f"Index '{OS_INDEX}' already exists — skipping.")
        return
    resp.raise_for_status()
    print(f"Index '{OS_INDEX}' created at {os_endpoint}.")


if __name__ == "__main__":
    create_index()
