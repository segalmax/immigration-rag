"""S3 client and object reads."""
import os

import boto3

REGION = os.environ["AWS_REGION"]
S3_CLIENT = boto3.client("s3", region_name=REGION)


def download_object_text(bucket: str, key: str) -> str:
    obj = S3_CLIENT.get_object(Bucket=bucket, Key=key)
    return obj["Body"].read().decode("utf-8")
