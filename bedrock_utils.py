"""
bedrock_utils.py — Amazon Bedrock helpers
Provides:
  embed(text)  → list[float]   using Titan Embeddings
  chat(prompt) → str           using Claude via Bedrock
"""
import os
import json
import boto3

AWS_REGION       = os.getenv("AWS_REGION", "us-east-1")
TITAN_MODEL_ID   = os.getenv("TITAN_EMBED_MODEL", "amazon.titan-embed-text-v1")
CLAUDE_MODEL_ID  = os.getenv("CLAUDE_MODEL_ID",   "anthropic.claude-3-sonnet-20240229-v1:0")

_client = None


def _get_client():
    global _client
    if _client is None:
        _client = boto3.client("bedrock-runtime", region_name=AWS_REGION)
    return _client


def embed(text: str) -> list:
    """Return a Titan embedding vector for the given text."""
    # TODO: implement
    client = _get_client()
    body   = json.dumps({"inputText": text})
    resp   = client.invoke_model(modelId=TITAN_MODEL_ID, body=body,
                                  contentType="application/json",
                                  accept="application/json")
    result = json.loads(resp["body"].read())
    return result["embedding"]


def chat(prompt: str, max_tokens: int = 1024) -> str:
    """Send a prompt to Claude and return the text response."""
    # TODO: implement
    client = _get_client()
    body   = json.dumps({
        "anthropic_version": "bedrock-2023-05-31",
        "max_tokens": max_tokens,
        "messages": [{"role": "user", "content": prompt}],
    })
    resp   = client.invoke_model(modelId=CLAUDE_MODEL_ID, body=body,
                                  contentType="application/json",
                                  accept="application/json")
    result = json.loads(resp["body"].read())
    return result["content"][0]["text"]
