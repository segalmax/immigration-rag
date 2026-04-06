"""
worker.py
SQS polling worker: downloads MD from S3, chunks, embeds with Titan, indexes in OpenSearch.

Usage:
    python worker.py
"""
import dotenv

dotenv.load_dotenv()

import json
import os
import re
import urllib.parse

import boto3
import src.bedrock_utils
import src.chunking
import src.opensearch_utils
import src.s3_utils

REGION = os.environ["AWS_REGION"]
S3_BUCKET = os.environ["S3_BUCKET"]
SQS_URL = os.environ["SQS_QUEUE_URL"]
OS_ENDPOINT = f"https://{os.environ['OS_HOST']}"
OS_INDEX = os.environ["OS_INDEX"]

POLL_WAIT = 5

SQS_CLIENT = boto3.client("sqs", region_name=REGION)


def poll_sqs() -> list:
    response = SQS_CLIENT.receive_message(
        QueueUrl=SQS_URL,
        MaxNumberOfMessages=1,
        WaitTimeSeconds=POLL_WAIT,
    )
    return response.get("Messages", [])


def delete_message(receipt: str) -> None:
    SQS_CLIENT.delete_message(QueueUrl=SQS_URL, ReceiptHandle=receipt)


def download_from_s3(s3_key: str) -> str:
    return src.s3_utils.download_object_text(S3_BUCKET, s3_key)


def extract_top_headers(text: str) -> tuple:
    h1 = h2 = h3 = ""
    for line in text.splitlines():
        if line.startswith("# ") and not h1:
            h1 = line[2:].strip()
        elif line.startswith("## ") and not h2:
            h2 = line[3:].strip()
        elif line.startswith("### ") and not h3:
            h3 = line[4:].strip()
        if h1 and h2 and h3:
            break
    return h1, h2, h3


def extract_source_url(text: str):
    match = re.search(r"^>\s*Source:\s*(https?://\S+)", text, re.MULTILINE)
    return match.group(1) if match else None


def extract_doc_metadata(text: str, category: str, s3_key: str) -> dict:
    if category == "uscis":
        h1, h2, h3 = extract_top_headers(text)
        return {
            "s3_key": s3_key,
            "category": "uscis",
            "volume": h1 or None,
            "part": h2 or None,
            "chapter": h3 or None,
            "source_url": extract_source_url(text),
            "_taxonomy": {h1, h2, h3},
        }
    return {
        "s3_key": s3_key,
        "category": "other",
        "volume": None,
        "part": None,
        "chapter": None,
        "source_url": None,
        "_taxonomy": set(),
    }


def category_for_s3_key(s3_key: str) -> str:
    if s3_key.startswith("uscis_policy_manual_clean/"):
        return "uscis"
    if s3_key.startswith("uploads/"):
        return "other"
    raise ValueError(f"Unsupported S3 key prefix: {s3_key}")


def s3_key_from_message(body: dict) -> tuple[str, str]:
    if "Records" in body:
        record = body["Records"][0]
        s3_key = urllib.parse.unquote_plus(record["s3"]["object"]["key"])
        return s3_key, category_for_s3_key(s3_key)
    if "s3_key" in body:
        s3_key = body["s3_key"]
        category = body.get("category") or category_for_s3_key(s3_key)
        return s3_key, category
    raise KeyError("Expected S3 event 'Records' or legacy 's3_key' message body")


def build_doc(chunk, meta: dict, chunk_index: int) -> dict:
    taxonomy = meta.get("_taxonomy", set())
    section_path = [value for value in chunk.metadata.values() if value and value not in taxonomy]
    return {
        "s3_key": meta["s3_key"],
        "category": meta["category"],
        "volume": meta["volume"],
        "part": meta["part"],
        "chapter": meta["chapter"],
        "source_url": meta["source_url"],
        "section_path": section_path,
        "text": chunk.page_content,
        "chunk_index": chunk_index,
    }


def process_message(msg: dict) -> None:
    body = json.loads(msg["Body"])
    s3_key, category = s3_key_from_message(body)
    receipt = msg["ReceiptHandle"]

    print(f"Processing {s3_key} (category={category})")
    text = download_from_s3(s3_key)
    meta = extract_doc_metadata(text, category, s3_key)
    chunks = src.chunking.chunk_document(text)

    for index, chunk in enumerate(chunks):
        doc = build_doc(chunk, meta, index)
        doc["vector"] = src.bedrock_utils.embed_text_for_titan(chunk.page_content)
        src.opensearch_utils.send_doc_to_opensearch(OS_ENDPOINT, OS_INDEX, doc)

    delete_message(receipt)
    print(f"  -> indexed {len(chunks)} chunks")


def run() -> None:
    src.bedrock_utils.load_opensearch_vector_spec(OS_ENDPOINT, OS_INDEX, src.opensearch_utils.OPENSEARCH_HTTP_AUTH)
    print(f"Worker started - polling {SQS_URL}")
    while True:
        messages = poll_sqs()
        if not messages:
            continue
        for msg in messages:
            process_message(msg)


if __name__ == "__main__":
    run()
