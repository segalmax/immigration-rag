"""
s3_utils.py — S3 helpers
Provides:
  download_from_s3(bucket, key, dest_path) → Path
  upload_to_s3(local_path, bucket, key)    → None
"""
import os
from pathlib import Path
import boto3

AWS_REGION = os.getenv("AWS_REGION", "us-east-1")
S3_BUCKET  = os.getenv("S3_BUCKET")

_s3 = None


def _get_s3():
    global _s3
    if _s3 is None:
        _s3 = boto3.client("s3", region_name=AWS_REGION)
    return _s3


def download_from_s3(bucket: str, key: str, dest_path: str) -> Path:
    """Download an S3 object to a local path and return the Path."""
    # TODO: implement
    dest = Path(dest_path)
    dest.parent.mkdir(parents=True, exist_ok=True)
    _get_s3().download_file(bucket, key, str(dest))
    return dest


def upload_to_s3(local_path: str, bucket: str, key: str) -> None:
    """Upload a local file to S3."""
    # TODO: implement
    _get_s3().upload_file(local_path, bucket, key)
