#!/usr/bin/env python3
"""
Manage OpenSearch Serverless collections: provision, backup, restore, teardown.

    --up   --col immig-col3   # provision + auto-restore if backup exists
    --down --col immig-col3   # backup + delete
    --down --all              # backup + delete all collections
    --backup --col immig-col3 # backup only (no delete)
    --restore --col immig-col3 # restore docs to existing collection

Lifecycle diagram: opensearch/lifecycle.md
"""
import argparse
import json
import os
import sys
import time
import dotenv
import boto3
import requests
import requests_aws4auth

dotenv.load_dotenv()

REGION       = "eu-central-1"
INDEX        = os.environ["OS_INDEX"]
SCROLL_SIZE  = 500
BULK_SIZE    = 500
HERE         = os.path.dirname(__file__)
DATA_DIR     = os.path.join(HERE, "data")
SCHEMA_FILE  = os.path.join(HERE, "index_schema.json")

COLLECTIONS = ["immig-col3"]


def _account_id() -> str:
    return boto3.client("sts").get_caller_identity()["Account"]


def _policies(col_name: str) -> dict:
    """Build all three policy dicts dynamically — no hardcoded account ID."""
    account_id = _account_id()
    return {
        "encryption": {
            "name": f"auto-{col_name}",
            "type": "encryption",
            "policy": json.dumps({
                "Rules": [{"Resource": [f"collection/{col_name}"], "ResourceType": "collection"}],
                "AWSOwnedKey": True,
            }),
        },
        "network": {
            "name": f"auto-{col_name}",
            "type": "network",
            "policy": json.dumps([{
                "Rules": [
                    {"Resource": [f"collection/{col_name}"], "ResourceType": "collection"},
                    {"Resource": [f"collection/{col_name}"], "ResourceType": "dashboard"},
                ],
                "AllowFromPublic": True,
            }]),
        },
        "access": {
            "name": f"access-policy-{col_name}",
            "type": "data",
            "policy": json.dumps([{
                "Rules": [
                    {"Resource": [f"collection/{col_name}"],
                     "Permission": ["aoss:CreateCollectionItems", "aoss:DeleteCollectionItems",
                                    "aoss:UpdateCollectionItems", "aoss:DescribeCollectionItems"],
                     "ResourceType": "collection"},
                    {"Resource": [f"index/{col_name}/*"],
                     "Permission": ["aoss:CreateIndex", "aoss:DeleteIndex", "aoss:UpdateIndex",
                                    "aoss:DescribeIndex", "aoss:ReadDocument", "aoss:WriteDocument"],
                     "ResourceType": "index"},
                ],
                "Principal": [
                    f"arn:aws:iam::{account_id}:user/kb_user",
                    f"arn:aws:iam::{account_id}:root",
                ],
            }]),
        },
    }


def _resolve(col_name: str) -> tuple[str, str]:
    client = boto3.client("opensearchserverless", region_name=REGION)
    cols = client.list_collections(collectionFilters={"name": col_name})["collectionSummaries"]
    assert cols, f"Collection '{col_name}' not found in AWS"
    col_id = cols[0]["id"]
    return col_id, f"https://{col_id}.{REGION}.aoss.amazonaws.com"


def _auth() -> requests_aws4auth.AWS4Auth:
    session = boto3.Session(profile_name="kb_user")
    creds = session.get_credentials().get_frozen_credentials()
    return requests_aws4auth.AWS4Auth(creds.access_key, creds.secret_key, REGION, "aoss", session_token=creds.token)


def _req(method: str, endpoint: str, path: str, body: dict = None) -> dict:
    url = endpoint + path
    kwargs = {"auth": _auth(), "headers": {"Content-Type": "application/json"}}
    if body:
        kwargs["json"] = body
    resp = requests.request(method, url, **kwargs)
    resp.raise_for_status()
    return resp.json() if resp.content else {}


def _backup_file(col_name: str) -> str:
    return os.path.join(DATA_DIR, f"opensearch_dump_{col_name}.jsonl")


def up(col_name: str, skip_restore: bool = False):
    client = boto3.client("opensearchserverless", region_name=REGION)
    policies = _policies(col_name)

    def create_or_skip(fn, **kwargs):
        try:
            fn(**kwargs); print(f"  created: {kwargs['name']}")
        except client.exceptions.ConflictException:
            print(f"  exists, skipping: {kwargs['name']}")

    cf = SCHEMA_FILE
    if os.path.exists(cf):
        saved = json.load(open(cf))
        enc_policy = json.dumps(saved["encryption_policy"]["policy"])
        net_policy = json.dumps(saved["network_policy"]["policy"])
        acc_policy = json.dumps(saved["access_policy"]["policy"])
    else:
        p = _policies(col_name)
        enc_policy, net_policy, acc_policy = p["encryption"]["policy"], p["network"]["policy"], p["access"]["policy"]

    print("Creating policies...")
    create_or_skip(client.create_security_policy, name=f"auto-{col_name}",           type="encryption", policy=enc_policy)
    create_or_skip(client.create_security_policy, name=f"auto-{col_name}",           type="network",    policy=net_policy)
    create_or_skip(client.create_access_policy,   name=f"access-policy-{col_name}",  type="data",       policy=acc_policy)

    print(f"Creating collection {col_name}...")
    try:
        resp   = client.create_collection(name=col_name, type="VECTORSEARCH", description="")
        col_id = resp["createCollectionDetail"]["id"]
        print(f"  created: id={col_id}, waiting for ACTIVE...")
    except client.exceptions.ConflictException:
        col_id = client.list_collections(collectionFilters={"name": col_name})["collectionSummaries"][0]["id"]
        print(f"  exists: id={col_id}, waiting for ACTIVE...")

    ep = f"https://{col_id}.{REGION}.aoss.amazonaws.com"
    while True:
        status = client.batch_get_collection(ids=[col_id])["collectionDetails"][0]["status"]
        if status == "ACTIVE": break
        assert status != "FAILED", "Collection entered FAILED state"
        print(f"  {status}... waiting 15s"); time.sleep(15)

    print("Waiting 20s for policies to propagate...")
    time.sleep(20)

    cf = SCHEMA_FILE
    assert os.path.exists(cf), f"No schema at {cf}. Run --down on a live collection first."
    config = json.load(open(cf))
    print(f"Creating index {INDEX} (from {cf})...")
    try:
        _req("PUT", ep, f"/{INDEX}", {"mappings": config["mapping"], "settings": {"index": config["settings"]}})
    except requests.exceptions.HTTPError as e:
        if e.response.status_code == 400 and "resource_already_exists_exception" in e.response.text:
            print(f"  index already exists, skipping.")
        else:
            raise
    print(f"✓ [{col_name}] up. Endpoint: {ep}")

    bf = _backup_file(col_name)
    if not skip_restore and os.path.exists(bf):
        restore(col_name, ep)
    elif not skip_restore:
        print(f"  no backup at {bf} — skipping restore.")


def export_config(col_name: str):
    """Export live mapping + settings + policies from AWS → data/opensearch_config_{name}.json"""
    client = boto3.client("opensearchserverless", region_name=REGION)
    col_id, ep = _resolve(col_name)

    index_resp = _req("GET", ep, f"/{INDEX}")
    mapping  = index_resp[INDEX]["mappings"]
    settings = {k: v for k, v in index_resp[INDEX]["settings"]["index"].items()
                if k not in ("creation_date", "uuid", "provided_name", "version")}

    enc = client.get_security_policy(name=f"auto-{col_name}", type="encryption")["securityPolicyDetail"]
    net = client.get_security_policy(name=f"auto-{col_name}", type="network")["securityPolicyDetail"]
    acc = client.get_access_policy(name=f"access-policy-{col_name}", type="data")["accessPolicyDetail"]

    config = {
        "collection": {"name": col_name, "type": "VECTORSEARCH"},
        "mapping":    mapping,
        "settings":   settings,
        "encryption_policy": {"name": enc["name"], "policy": enc["policy"]},
        "network_policy":    {"name": net["name"], "policy": net["policy"]},
        "access_policy":     {"name": acc["name"], "policy": acc["policy"]},
    }
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(SCHEMA_FILE, "w") as f:
        json.dump(config, f, indent=2, default=str)
    print(f"✓ [{col_name}] config exported → {SCHEMA_FILE}")


def backup(col_name: str):
    _, ep = _resolve(col_name)
    resp      = _req("GET", ep, f"/{INDEX}/_search?scroll=2m", {"size": SCROLL_SIZE, "query": {"match_all": {}}})
    scroll_id = resp["_scroll_id"]
    total     = resp["hits"]["total"]["value"]
    print(f"  [{col_name}] {total} docs to back up...")
    count = 0
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(_backup_file(col_name), "w") as f:
        while True:
            hits = resp["hits"]["hits"]
            if not hits: break
            for doc in hits:
                f.write(json.dumps({"_id": doc["_id"], "_source": doc["_source"]}) + "\n")
                count += 1
            resp      = _req("POST", ep, "/_search/scroll", {"scroll": "2m", "scroll_id": scroll_id})
            scroll_id = resp["_scroll_id"]
    if count:
        _req("DELETE", ep, "/_search/scroll", {"scroll_id": scroll_id})
    print(f"✓ [{col_name}] {count} docs → {_backup_file(col_name)}")


def delete(col_name: str):
    client = boto3.client("opensearchserverless", region_name=REGION)
    col_id, _ = _resolve(col_name)
    client.delete_collection(id=col_id)
    print(f"✓ [{col_name}] collection deleted.")


def down(col_name: str, skip_backup: bool = False):
    export_config(col_name)
    if not skip_backup:
        backup(col_name)
    delete(col_name)


def restore(col_name: str, endpoint: str = None):
    if endpoint is None:
        _, endpoint = _resolve(col_name)
    bf = _backup_file(col_name)
    assert os.path.exists(bf), f"No backup at {bf}"
    with open(bf) as f:
        docs = [json.loads(line) for line in f if line.strip()]
    print(f"  [{col_name}] restoring {len(docs)} docs...")
    auth  = _auth()
    count = 0
    for i in range(0, len(docs), BULK_SIZE):
        batch  = docs[i: i + BULK_SIZE]
        ndjson = "".join(
            json.dumps({"index": {"_id": d["_id"]}}) + "\n" + json.dumps(d["_source"]) + "\n"
            for d in batch
        )
        resp = requests.post(endpoint + f"/{INDEX}/_bulk", auth=auth,
                             data=ndjson.encode(), headers={"Content-Type": "application/x-ndjson"})
        resp.raise_for_status()
        errors = [item for item in resp.json()["items"] if "error" in item.get("index", {})]
        if errors: print(f"  WARN: {len(errors)} errors in batch {i // BULK_SIZE + 1}")
        count += len(batch)
        print(f"  {count}/{len(docs)}...")
    print(f"✓ [{col_name}] restored {count} docs.")


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Manage OpenSearch Serverless collections")
    p.add_argument("--col",          default=None,        help="Collection name (e.g. immig-col3)")
    p.add_argument("--all",          action="store_true", help="Run on all known collections")
    p.add_argument("--up",           action="store_true", help="Provision + auto-restore if backup exists")
    p.add_argument("--down",         action="store_true", help="Backup + delete collection")
    p.add_argument("--backup",       action="store_true", help="Backup docs only (no delete)")
    p.add_argument("--restore",      action="store_true", help="Restore docs into existing collection")
    p.add_argument("--skip-backup",  action="store_true", help="Skip backup when running --down")
    p.add_argument("--skip-restore", action="store_true", help="Skip restore when running --up")
    return p.parse_args()


def _cols(args) -> list[str]:
    if args.all:
        return COLLECTIONS
    assert args.col, "Specify --col NAME or --all"
    assert args.col in COLLECTIONS, f"Unknown: '{args.col}'. Known: {COLLECTIONS}"
    return [args.col]


def main():
    args = parse_args()
    if args.up:
        for col in _cols(args):
            print(f"\n=== {col} ==="); up(col, skip_restore=args.skip_restore)
    elif args.down:
        for col in _cols(args):
            print(f"\n=== {col} ==="); down(col, skip_backup=args.skip_backup)
    elif args.backup:
        for col in _cols(args):
            print(f"\n=== {col} ==="); backup(col)
    elif args.restore:
        for col in _cols(args):
            print(f"\n=== {col} ==="); restore(col)
    else:
        print("Specify --up, --down, --backup, or --restore"); sys.exit(1)


if __name__ == "__main__":
    main()
