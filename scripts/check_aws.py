"""
scripts/check_aws.py
Connectivity check: S3, SQS, OpenSearch, Bedrock Claude, Bedrock Titan v2.
Reads config from .env (or env vars already set in the environment).

Usage:
    python check_aws.py
"""
import json
import os
import dotenv
import boto3
import requests
import requests_aws4auth

dotenv.load_dotenv()

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


def _aoss_auth() -> requests_aws4auth.AWS4Auth:
    creds = boto3.Session().get_credentials().get_frozen_credentials()
    return requests_aws4auth.AWS4Auth(creds.access_key, creds.secret_key, REGION, "aoss", session_token=creds.token)


def check_opensearch():
    resp = requests.get(OS_ENDPOINT + f"/{OS_INDEX}", auth=_aoss_auth(), timeout=10)
    return f"HTTP {resp.status_code} — index={OS_INDEX}"


def check_claude():
    client = boto3.client("bedrock-runtime", region_name=REGION)
    body = json.dumps({"anthropic_version": "bedrock-2023-05-31", "max_tokens": 10, "messages": [{"role": "user", "content": "hi"}]})
    out = json.loads(client.invoke_model(modelId=CLAUDE, body=body)["body"].read())
    return f"stop_reason={out['stop_reason']}"


def check_titan():
    client = boto3.client("bedrock-runtime", region_name=REGION)
    out = json.loads(client.invoke_model(modelId=TITAN, body=json.dumps({"inputText": "test"}))["body"].read())
    return f"embedding dim={len(out['embedding'])}"


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
