#!/usr/bin/env python3
"""
Manage OpenSearch Serverless collections: provision, backup, restore, teardown.
See lifecycle.md in this folder for the full diagram.

Usage:
    --up --col immig-col3        # provision + auto-restore if backup exists
    --down --all                 # backup + delete all collections
    --backup --col immig-col3    # backup only (no delete)
    --restore --col immig-col3   # restore docs to existing collection
"""
import argparse
import json
import os
import sys
import time
import boto3
import requests
from requests_aws4auth import AWS4Auth

REGION = "eu-central-1"
INDEX = "kb_index"
SCROLL_SIZE = 500
BULK_SIZE = 500
DATA_DIR = os.path.join(os.path.dirname(__file__), "data")

# Known collections: name → policy names (IDs looked up dynamically)
COLLECTIONS = {
    "immig-col3": {
        "access_policy": "access-policy-immig-col3",
        "network_policy": "auto-immig-col3",
        "encryption_policy": "auto-immig-col3",
    },
}


def _resolve(col_name: str) -> tuple[str, str]:
    """Return (collection_id, endpoint) for a collection name."""
    client = boto3.client("opensearchserverless", region_name=REGION)
    cols = client.list_collections(collectionFilters={"name": col_name})["collectionSummaries"]
    assert cols, f"Collection '{col_name}' not found in AWS"
    col_id = cols[0]["id"]
    return col_id, f"https://{col_id}.{REGION}.aoss.amazonaws.com"


def _auth(profile: str = "kb_user") -> AWS4Auth:
    session = boto3.Session(profile_name=profile)
    creds = session.get_credentials().get_frozen_credentials()
    return AWS4Auth(creds.access_key, creds.secret_key, REGION, "aoss", session_token=creds.token)


def _req(method: str, endpoint: str, path: str, body: dict = None) -> dict:
    url = endpoint + path
    kwargs = {"auth": _auth(), "headers": {"Content-Type": "application/json"}}
    if body:
        kwargs["json"] = body
    resp = requests.request(method, url, **kwargs)
    resp.raise_for_status()
    return resp.json() if resp.content else {}


def _config_file(col_name: str) -> str:
    return os.path.join(DATA_DIR, f"opensearch_config_{col_name}.json")


def _backup_file(col_name: str) -> str:
    return os.path.join(DATA_DIR, f"opensearch_dump_{col_name}.jsonl")


def export(col_name: str, meta: dict):
    client = boto3.client("opensearchserverless", region_name=REGION)
    col_id, ep = _resolve(col_name)
    config = {}

    detail = client.batch_get_collection(ids=[col_id])["collectionDetails"][0]
    config["collection"] = {"name": detail["name"], "type": detail["type"], "description": detail.get("description", "")}

    config["mapping"] = _req("GET", ep, f"/{INDEX}/_mapping")[INDEX]["mappings"]
    raw = _req("GET", ep, f"/{INDEX}/_settings")[INDEX]["settings"]["index"]
    config["settings"] = {
        "number_of_shards": raw["number_of_shards"],
        "number_of_replicas": raw["number_of_replicas"],
        "knn": raw["knn"],
        "knn.algo_param.ef_search": raw["knn.algo_param"]["ef_search"],
    }

    config["access_policy"]     = {"name": meta["access_policy"],     "policy": client.get_access_policy(name=meta["access_policy"], type="data")["accessPolicyDetail"]["policy"]}
    config["network_policy"]    = {"name": meta["network_policy"],    "policy": client.get_security_policy(name=meta["network_policy"], type="network")["securityPolicyDetail"]["policy"]}
    config["encryption_policy"] = {"name": meta["encryption_policy"], "policy": client.get_security_policy(name=meta["encryption_policy"], type="encryption")["securityPolicyDetail"]["policy"]}

    out = _config_file(col_name)
    with open(out, "w") as f:
        json.dump(config, f, indent=2)
    dim = config["mapping"]["properties"]["vector"]["dimension"]
    print(f"✓ [{col_name}] config → {out}  (kNN dim={dim})")


def backup(col_name: str, meta: dict):
    _, ep = _resolve(col_name)
    resp = _req("GET", ep, f"/{INDEX}/_search?scroll=2m", {"size": SCROLL_SIZE, "query": {"match_all": {}}})
    scroll_id = resp["_scroll_id"]
    total = resp["hits"]["total"]["value"]
    print(f"  [{col_name}] {total} docs to back up...")
    count = 0
    out = _backup_file(col_name)
    with open(out, "w") as f:
        while True:
            hits = resp["hits"]["hits"]
            if not hits:
                break
            for doc in hits:
                f.write(json.dumps({"_id": doc["_id"], "_source": doc["_source"]}) + "\n")
                count += 1
            resp = _req("POST", ep, "/_search/scroll", {"scroll": "2m", "scroll_id": scroll_id})
            scroll_id = resp["_scroll_id"]
    if count:
        _req("DELETE", ep, "/_search/scroll", {"scroll_id": scroll_id})
    print(f"✓ [{col_name}] {count} docs → {out}")


def delete(col_name: str):
    client = boto3.client("opensearchserverless", region_name=REGION)
    col_id, _ = _resolve(col_name)
    client.delete_collection(id=col_id)
    print(f"✓ [{col_name}] collection deleted.")


def up(col_name: str, skip_restore: bool = False):
    config_file = _config_file(col_name)
    assert os.path.exists(config_file), f"No config at {config_file} — run --backup first."
    config = json.load(open(config_file))
    client = boto3.client("opensearchserverless", region_name=REGION)
    target = config["collection"]["name"]

    def swap(policy):
        s = json.dumps(policy)
        assert col_name in s or col_name == target, f"Expected '{col_name}' in policy — wrong config file?"
        return s.replace(col_name, target)

    ap_name = f"access-policy-{target}"
    np_name = config["network_policy"]["name"].replace(col_name, target)
    ep_name = config["encryption_policy"]["name"].replace(col_name, target)

    def create_or_skip(fn, **kwargs):
        try:
            fn(**kwargs); print(f"  created: {kwargs.get('name')}")
        except client.exceptions.ConflictException:
            print(f"  exists, skipping: {kwargs.get('name')}")

    print("Creating policies...")
    create_or_skip(client.create_security_policy, name=ep_name, type="encryption", policy=swap(config["encryption_policy"]["policy"]))
    create_or_skip(client.create_security_policy, name=np_name, type="network",    policy=swap(config["network_policy"]["policy"]))
    create_or_skip(client.create_access_policy,   name=ap_name, type="data",       policy=swap(config["access_policy"]["policy"]))

    print(f"Creating collection {target}...")
    try:
        resp = client.create_collection(name=target, type=config["collection"]["type"], description=config["collection"]["description"])
        new_id = resp["createCollectionDetail"]["id"]
        print(f"  created: id={new_id}, waiting for ACTIVE...")
    except client.exceptions.ConflictException:
        new_id = client.list_collections(collectionFilters={"name": target})["collectionSummaries"][0]["id"]
        print(f"  exists, skipping: id={new_id}, waiting for ACTIVE...")
    new_ep = f"https://{new_id}.{REGION}.aoss.amazonaws.com"

    while True:
        status = client.batch_get_collection(ids=[new_id])["collectionDetails"][0]["status"]
        if status == "ACTIVE": break
        print(f"  {status}... waiting 15s"); time.sleep(15)

    print("Waiting 20s for policies to propagate...")
    time.sleep(20)

    print(f"Creating index {INDEX}...")
    try:
        _req("PUT", new_ep, f"/{INDEX}", {"mappings": config["mapping"], "settings": {"index": config["settings"]}})
        print(f"✓ [{col_name}] up. Endpoint: {new_ep}")
    except requests.exceptions.HTTPError as e:
        if e.response.status_code == 400 and "resource_already_exists_exception" in e.response.text:
            print(f"  index already exists, skipping.")
            print(f"✓ [{col_name}] up. Endpoint: {new_ep}")
        else:
            raise

    backup_file = _backup_file(col_name)
    if not skip_restore and os.path.exists(backup_file):
        restore(col_name, new_ep)
    elif not skip_restore:
        print(f"  no backup file found at {backup_file} — skipping restore.")


def down(col_name: str, meta: dict, skip_backup: bool = False):
    if not skip_backup:
        export(col_name, meta)
        backup(col_name, meta)
    delete(col_name)


def restore(col_name: str, endpoint: str):
    backup_file = _backup_file(col_name)
    assert os.path.exists(backup_file), f"No backup file at {backup_file}"
    with open(backup_file) as f:
        docs = [json.loads(line) for line in f if line.strip()]
    print(f"  [{col_name}] restoring {len(docs)} docs...")
    auth = _auth()
    count = 0
    for i in range(0, len(docs), BULK_SIZE):
        batch = docs[i: i + BULK_SIZE]
        ndjson = "".join(
            json.dumps({"index": {"_id": d["_id"]}}) + "\n" + json.dumps(d["_source"]) + "\n"
            for d in batch
        )
        resp = requests.post(endpoint + f"/{INDEX}/_bulk", auth=auth, data=ndjson.encode(), headers={"Content-Type": "application/x-ndjson"})
        resp.raise_for_status()
        errors = [item for item in resp.json()["items"] if "error" in item.get("index", {})]
        if errors: print(f"  WARN: {len(errors)} errors in batch {i // BULK_SIZE + 1}")
        count += len(batch)
        print(f"  {count}/{len(docs)}...")
    print(f"✓ [{col_name}] restored {count} docs.")


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Manage OpenSearch Serverless collections")
    p.add_argument("--col",          dest="col",          default=None,        help="Collection name (e.g. immig-col3)")
    p.add_argument("--all",          dest="all",          action="store_true", help="Run on all known collections")
    p.add_argument("--up",           dest="up",           action="store_true", help="Provision collection + auto-restore if backup exists")
    p.add_argument("--down",         dest="down",         action="store_true", help="Backup + delete collection")
    p.add_argument("--backup",       dest="backup",       action="store_true", help="Backup docs to file (no delete)")
    p.add_argument("--restore",      dest="restore",      action="store_true", help="Restore docs from backup into existing collection")
    p.add_argument("--skip-backup",  dest="skip_backup",  action="store_true", help="Skip backup when running --down")
    p.add_argument("--skip-restore", dest="skip_restore", action="store_true", help="Skip restore when running --up")
    return p.parse_args()


def _cols(args) -> list[tuple[str, dict]]:
    if args.all:
        return list(COLLECTIONS.items())
    assert args.col, "Specify --col NAME or --all"
    assert args.col in COLLECTIONS, f"Unknown collection '{args.col}'. Known: {list(COLLECTIONS)}"
    return [(args.col, COLLECTIONS[args.col])]


def main():
    args = parse_args()

    if args.up:
        for col_name, _ in _cols(args):
            print(f"\n=== {col_name} ===")
            up(col_name, skip_restore=args.skip_restore)
    elif args.down:
        for col_name, meta in _cols(args):
            print(f"\n=== {col_name} ===")
            down(col_name, meta, skip_backup=args.skip_backup)
    elif args.backup:
        for col_name, meta in _cols(args):
            print(f"\n=== {col_name} ===")
            export(col_name, meta)
            backup(col_name, meta)
    elif args.restore:
        for col_name, _ in _cols(args):
            print(f"\n=== {col_name} ===")
            col_id, ep = _resolve(col_name)
            restore(col_name, ep)
    else:
        print("Specify --up, --down, --backup, or --restore")
        sys.exit(1)


if __name__ == "__main__":
    main()
