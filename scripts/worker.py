"""
scripts/worker.py
SQS polling worker: downloads MD from S3, chunks, embeds with Titan, indexes in OpenSearch.

Usage:
    python scripts/worker.py
"""
import json
import os
import re
import time

import boto3
import dotenv
import langchain_text_splitters
import requests
import requests_aws4auth

dotenv.load_dotenv()

REGION        = os.environ["AWS_REGION"]
S3_BUCKET     = os.environ["S3_BUCKET"]
SQS_URL       = os.environ["SQS_QUEUE_URL"]
OS_ENDPOINT   = f"https://{os.environ['OS_HOST']}"
OS_INDEX      = os.environ["OS_INDEX"]
TITAN_MODEL   = os.environ["TITAN_EMBED_MODEL"]

HEADERS_TO_SPLIT = [("#", "h1"), ("##", "h2"), ("###", "h3")]
MAX_CHUNK_CHARS  = 2000   # ~500 tokens at 4 chars/token
CHUNK_OVERLAP    = 200
POLL_WAIT        = 5      # SQS WaitTimeSeconds


# ── AWS clients (lazy singletons) ───────────────────────────────────────────

_sqs      = None
_s3       = None
_bedrock  = None
_os_auth  = None


def sqs_client():
    global _sqs
    if _sqs is None:
        _sqs = boto3.client("sqs", region_name=REGION)
    return _sqs


def s3_client():
    global _s3
    if _s3 is None:
        _s3 = boto3.client("s3", region_name=REGION)
    return _s3


def bedrock_client():
    global _bedrock
    if _bedrock is None:
        _bedrock = boto3.client("bedrock-runtime", region_name=REGION)
    return _bedrock


def os_auth():
    global _os_auth
    if _os_auth is None:
        creds = boto3.Session().get_credentials().get_frozen_credentials()
        _os_auth = requests_aws4auth.AWS4Auth(
            creds.access_key, creds.secret_key, REGION, "aoss", session_token=creds.token
        )
    return _os_auth


# ── SQS helpers ─────────────────────────────────────────────────────────────

def poll_sqs() -> list:
    resp = sqs_client().receive_message(
        QueueUrl=SQS_URL, MaxNumberOfMessages=1, WaitTimeSeconds=POLL_WAIT
    )
    return resp.get("Messages", [])


def delete_message(receipt: str) -> None:
    sqs_client().delete_message(QueueUrl=SQS_URL, ReceiptHandle=receipt)


# ── S3 helpers ───────────────────────────────────────────────────────────────

def download_from_s3(s3_key: str) -> str:
    obj = s3_client().get_object(Bucket=S3_BUCKET, Key=s3_key)
    return obj["Body"].read().decode("utf-8")


# ── Metadata extraction ──────────────────────────────────────────────────────

def extract_top_headers(text: str) -> tuple:
    h1 = h2 = h3 = ""
    for line in text.splitlines():
        if line.startswith("# ")   and not h1: h1 = line[2:].strip()
        elif line.startswith("## ") and not h2: h2 = line[3:].strip()
        elif line.startswith("### ") and not h3: h3 = line[4:].strip()
        if h1 and h2 and h3:
            break
    return h1, h2, h3


def extract_source_url(text: str):
    m = re.search(r'^>\s*Source:\s*(https?://\S+)', text, re.MULTILINE)
    return m.group(1) if m else None


def extract_doc_metadata(text: str, category: str, s3_key: str) -> dict:
    if category == "uscis":
        h1, h2, h3 = extract_top_headers(text)
        return {
            "s3_key":          s3_key,
            "category":        "uscis",
            "volume":          h1 or None,
            "part":            h2 or None,
            "chapter":         h3 or None,
            "source_url":      extract_source_url(text),
            "_taxonomy":       {h1, h2, h3},
        }
    return {
        "s3_key":     s3_key,
        "category":   "other",
        "volume":     None,
        "part":       None,
        "chapter":    None,
        "source_url": None,
        "_taxonomy":  set(),
    }


# ── Chunking ─────────────────────────────────────────────────────────────────

def chunk_document(text: str) -> list:
    header_splitter = langchain_text_splitters.MarkdownHeaderTextSplitter(
        headers_to_split_on=HEADERS_TO_SPLIT, strip_headers=False
    )
    char_splitter = langchain_text_splitters.RecursiveCharacterTextSplitter(
        chunk_size=MAX_CHUNK_CHARS, chunk_overlap=CHUNK_OVERLAP
    )
    chunks = header_splitter.split_text(text)
    result = []
    for chunk in chunks:
        if len(chunk.page_content) > MAX_CHUNK_CHARS:
            sub = char_splitter.create_documents([chunk.page_content], metadatas=[chunk.metadata])
            result.extend(sub)
        else:
            result.append(chunk)
    return result


def build_doc(chunk, meta: dict, chunk_index: int) -> dict:
    taxonomy     = meta.get("_taxonomy", set())
    section_path = [v for v in chunk.metadata.values() if v and v not in taxonomy]
    return {
        "s3_key":       meta["s3_key"],
        "category":     meta["category"],
        "volume":       meta["volume"],
        "part":         meta["part"],
        "chapter":      meta["chapter"],
        "source_url":   meta["source_url"],
        "section_path": section_path,
        "text":         chunk.page_content,
        "chunk_index":  chunk_index,
    }


# ── Embedding ────────────────────────────────────────────────────────────────

def embed_text(text: str) -> list:
    body = json.dumps({"inputText": text, "dimensions": 1024, "normalize": True})
    resp = bedrock_client().invoke_model(
        body=body, modelId=TITAN_MODEL, contentType="application/json", accept="application/json"
    )
    return json.loads(resp["body"].read())["embedding"]


# ── OpenSearch indexing ──────────────────────────────────────────────────────

def index_doc(doc: dict) -> None:
    resp = requests.post(
        f"{OS_ENDPOINT}/{OS_INDEX}/_doc",
        auth=os_auth(),
        json=doc,
        headers={"Content-Type": "application/json"},
        timeout=30,
    )
    resp.raise_for_status()


# ── Message processing ───────────────────────────────────────────────────────

def process_message(msg: dict) -> None:
    body     = json.loads(msg["Body"])
    s3_key   = body["s3_key"]
    category = body.get("category", "other")
    receipt  = msg["ReceiptHandle"]

    print(f"Processing {s3_key} (category={category})")
    text   = download_from_s3(s3_key)
    meta   = extract_doc_metadata(text, category, s3_key)
    chunks = chunk_document(text)

    for i, chunk in enumerate(chunks):
        doc           = build_doc(chunk, meta, i)
        doc["vector"] = embed_text(chunk.page_content)
        index_doc(doc)

    delete_message(receipt)
    print(f"  → indexed {len(chunks)} chunks")


# ── Main loop ────────────────────────────────────────────────────────────────

def run():
    print(f"Worker started — polling {SQS_URL}")
    while True:
        messages = poll_sqs()
        if not messages:
            continue
        for msg in messages:
            process_message(msg)


if __name__ == "__main__":
    run()
