import os

AWS_REGION      = os.getenv("AWS_REGION", "us-east-1")
TITAN_MODEL_ID  = os.getenv("TITAN_EMBED_MODEL", "amazon.titan-embed-text-v1")
CLAUDE_MODEL_ID = os.getenv("CLAUDE_MODEL_ID", "anthropic.claude-3-sonnet-20240229-v1:0")


def embed(text: str) -> list:
    raise NotImplementedError


def chat(prompt: str, max_tokens: int = 1024) -> str:
    raise NotImplementedError
