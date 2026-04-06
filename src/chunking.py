"""Markdown-aware chunking for policy manual text."""
import langchain_text_splitters

HEADERS_TO_SPLIT = [("#", "h1"), ("##", "h2"), ("###", "h3")]
MAX_CHUNK_CHARS = 2000
CHUNK_OVERLAP = 200


def chunk_document(text: str) -> list:
    header_splitter = langchain_text_splitters.MarkdownHeaderTextSplitter(
        headers_to_split_on=HEADERS_TO_SPLIT,
        strip_headers=False,
    )
    char_splitter = langchain_text_splitters.RecursiveCharacterTextSplitter(
        chunk_size=MAX_CHUNK_CHARS,
        chunk_overlap=CHUNK_OVERLAP,
    )
    chunks = header_splitter.split_text(text)
    result = []
    for chunk in chunks:
        if len(chunk.page_content) > MAX_CHUNK_CHARS:
            sub_chunks = char_splitter.create_documents([chunk.page_content], metadatas=[chunk.metadata])
            result.extend(sub_chunks)
            continue
        result.append(chunk)
    return result
