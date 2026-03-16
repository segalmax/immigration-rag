"""
worker.py — SQS Worker
Polls the SQS queue for S3 ObjectCreated events.
For each event:
  1. Downloads the file from S3 (s3_utils.download_from_s3)
  2. Optionally extracts text with Textract
  3. Chunks the text (chunking.chunk_text)
  4. Embeds each chunk (bedrock_utils.embed)
  5. Indexes chunks into OpenSearch (opensearch_utils.index)

Run with:  python worker.py

TODO: implement once AWS infra is provisioned.
"""
import os
import time
import json
import boto3
from dotenv import load_dotenv

load_dotenv()

SQS_QUEUE_URL = os.getenv("SQS_QUEUE_URL")
AWS_REGION    = os.getenv("AWS_REGION", "us-east-1")


def process_message(msg: dict) -> None:
    """Handle a single SQS message (S3 ObjectCreated event)."""
    body = json.loads(msg["Body"])
    # TODO: parse S3 key from body, download, chunk, embed, index
    print(f"[worker] received message: {body}")


def run() -> None:
    """Main polling loop."""
    sqs = boto3.client("sqs", region_name=AWS_REGION)
    print("[worker] starting — polling", SQS_QUEUE_URL)
    while True:
        resp = sqs.receive_message(
            QueueUrl=SQS_QUEUE_URL,
            MaxNumberOfMessages=10,
            WaitTimeSeconds=20,          # long-polling
        )
        messages = resp.get("Messages", [])
        for msg in messages:
            try:
                process_message(msg)
                sqs.delete_message(
                    QueueUrl=SQS_QUEUE_URL,
                    ReceiptHandle=msg["ReceiptHandle"],
                )
            except Exception as e:
                print(f"[worker] error processing message: {e}")
        if not messages:
            time.sleep(1)


if __name__ == "__main__":
    run()
