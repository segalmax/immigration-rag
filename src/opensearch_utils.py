import os

OS_HOST    = os.getenv("OS_HOST")
OS_INDEX   = os.getenv("OS_INDEX", "uscis-policy")
AWS_REGION = os.getenv("AWS_REGION", "us-east-1")


def index(doc_id: str, vector: list, metadata: dict) -> None:
    raise NotImplementedError


def search(query_vector: list, k: int = 5) -> list:
    raise NotImplementedError
