import os

MAX_TOKENS = int(os.getenv("CHUNK_MAX_TOKENS", 512))


def chunk_document(text: str, source_path: str) -> list:
    """Returns list of dicts: {"text": str, "source": str, "section": str}"""
    raise NotImplementedError
