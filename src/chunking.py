"""
chunking.py — Text chunking utilities
Splits cleaned markdown documents into chunks suitable for embedding.

Strategy:
  1. Split on ## section headers (each section becomes a candidate chunk)
  2. If a section exceeds max_tokens, split further on paragraph boundaries
  3. Add metadata (volume, part, chapter, section_title) to each chunk

TODO: tune max_tokens and overlap once Titan embedding limits are confirmed.
"""
import re
from typing import Generator


MAX_TOKENS  = 512   # target chunk size (Titan Embeddings v1 max = 8192, but smaller = better retrieval)
OVERLAP     = 50    # token overlap between consecutive paragraph chunks


def chunk_text(
    text: str,
    source_path: str = "",
    max_tokens: int = MAX_TOKENS,
) -> list:
    """
    Split a markdown document into chunks.
    Returns list of dicts: {"text": str, "source": str, "section": str}

    TODO: implement — currently returns the whole text as one chunk.
    """
    return [{"text": text, "source": source_path, "section": ""}]


def _split_on_sections(text: str) -> list:
    """Split on ## headings, return list of (heading, body) tuples."""
    # TODO: implement
    pattern = re.compile(r'^(## .+)$', re.MULTILINE)
    parts   = pattern.split(text)
    chunks  = []
    it      = iter(parts)
    preamble = next(it, "")
    if preamble.strip():
        chunks.append(("", preamble))
    for heading, body in zip(it, it):
        chunks.append((heading.strip(), body.strip()))
    return chunks
