"""
scripts/check_aws.py
Connectivity check: S3, SQS, OpenSearch, Bedrock Claude, Bedrock Titan v2.
Reads config from .env (or env vars already set in the environment).

Usage:
    python scripts/check_aws.py   (from project root)
"""
import json
import os
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

import dotenv

dotenv.load_dotenv()

import boto3
import requests
import src.bedrock_utils
import src.opensearch_utils

REGION        = os.environ["AWS_REGION"]
S3_BUCKET     = os.environ["S3_BUCKET"]
SQS_QUEUE_URL = os.environ["SQS_QUEUE_URL"]
OS_ENDPOINT   = f"https://{os.environ['OS_HOST']}"
OS_INDEX      = os.environ["OS_INDEX"]
CLAUDE        = os.environ["CLAUDE_MODEL_ID"]
TITAN         = os.environ["TITAN_EMBED_MODEL"]


def check(label: str, fn):
    try:
        print(f"  OK  {label}: {fn()}")
    except Exception as e:
        print(f"  FAIL {label}: {e}")


def check_s3():
    boto3.client("s3", region_name=REGION).head_bucket(Bucket=S3_BUCKET)
    return S3_BUCKET


def check_sqs():
    attrs = boto3.client("sqs", region_name=REGION).get_queue_attributes(
        QueueUrl=SQS_QUEUE_URL, AttributeNames=["ApproximateNumberOfMessages"]
    )["Attributes"]
    return f"~{attrs['ApproximateNumberOfMessages']} message(s) in queue"


def check_opensearch():
    resp = requests.get(OS_ENDPOINT + f"/{OS_INDEX}", auth=src.opensearch_utils.OPENSEARCH_HTTP_AUTH, timeout=10)
    return f"HTTP {resp.status_code} — index={OS_INDEX}"


def check_claude():
    body = json.dumps({"anthropic_version": "bedrock-2023-05-31", "max_tokens": 10, "messages": [{"role": "user", "content": "hi"}]})
    out = src.bedrock_utils.invoke_claude(body, model_id=CLAUDE)
    return f"stop_reason={out['stop_reason']}"


def check_titan():
    src.bedrock_utils.load_opensearch_vector_spec(OS_ENDPOINT, OS_INDEX, src.opensearch_utils.OPENSEARCH_HTTP_AUTH)
    body = src.bedrock_utils.titan_embed_invoke_body_json("test")
    out = json.loads(
        src.bedrock_utils.BEDROCK_RUNTIME.invoke_model(
            modelId=TITAN, body=body, contentType="application/json", accept="application/json"
        )["body"].read()
    )
    got = len(out["embedding"])
    want = src.bedrock_utils.embedding_dimension()
    assert got == want, f"Titan embedding dim {got} != index mapping {want}"
    return f"embedding dim={got} (from OpenSearch _mapping)"


def main():
    print(f"\nConnectivity check — region: {REGION}\n")
    check("S3",         check_s3)
    check("SQS",        check_sqs)
    check("OpenSearch", check_opensearch)
    check("Claude",     check_claude)
    check("Titan v2",   check_titan)
    print()


if __name__ == "__main__":
    main()
