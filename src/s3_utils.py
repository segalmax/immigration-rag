import os

AWS_REGION = os.getenv("AWS_REGION", "us-east-1")
S3_BUCKET  = os.getenv("S3_BUCKET")


def download(bucket: str, key: str, dest_path: str):
    raise NotImplementedError


def upload(local_path: str, bucket: str, key: str) -> None:
    raise NotImplementedError
