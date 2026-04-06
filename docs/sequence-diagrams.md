# Sequence Diagrams

## 1. Ingest (File Upload)

```mermaid
%%{init: {'theme': 'base', 'themeVariables': {'primaryColor': '#4f46e5', 'primaryTextColor': '#fff', 'primaryBorderColor': '#3730a3', 'secondaryColor': '#0891b2', 'secondaryTextColor': '#fff', 'tertiaryColor': '#059669', 'tertiaryTextColor': '#fff', 'lineColor': '#6b7280', 'textColor': '#111827', 'noteBkgColor': '#fef9c3', 'noteTextColor': '#713f12', 'activationBkgColor': '#e0e7ff', 'activationBorderColor': '#4f46e5', 'loopTextColor': '#4f46e5', 'labelBoxBkgColor': '#f0fdf4', 'labelBoxBorderColor': '#059669', 'labelTextColor': '#065f46'}}}%%
sequenceDiagram
    participant C as Client
    participant F as Flask App
    participant S3 as S3
    participant SQS as SQS Queue
    participant W as Worker
    participant T as Titan Embedder
    participant OS as OpenSearch

    Note over C: User selects file + category (USCIS or Other)
    Note over C: If USCIS: JS reads H1/H2/H3 from file, shows preview

    C->>F: POST /v1/uploads/presign {filename, category, h1, h2, h3}
    Note over F: USCIS key = uscis_policy_manual_clean/{h1_slug}/{h2_slug}/{filename}
    Note over F: Other key  = uploads/{filename}
    F->>S3: generate presigned PUT URL for key
    S3-->>F: presigned URL
    F-->>C: {url, key}

    C->>S3: PUT presigned_url (file bytes)
    S3-->>C: 200 OK
    S3->>SQS: ObjectCreated event

    loop Worker polling (WaitTimeSeconds=5)
        W->>SQS: receive_message
        SQS-->>W: {Records:[...]}
    end

    W->>S3: GetObject(s3_key)
    S3-->>W: file content (.md)

    opt preprocess (LP — only for raw/noisy files)
        W->>W: normalize text (strip footnotes, fix encoding)
    end

    Note over W: If USCIS: extract H1→volume, H2→part, H3→chapter, source_url from blockquote
    W->>W: chunk via MarkdownHeaderTextSplitter → section_path per chunk
    Note over W: Oversized chunks (>2000 chars) → RecursiveCharacterTextSplitter

    W->>T: embed chunk.page_content
    T-->>W: vector[1024]

    Note over W: doc = {s3_key, category, volume, part, chapter, source_url, section_path, text, chunk_index, vector}
    W->>OS: POST /{index}/_doc
    OS-->>W: 200 OK

    W->>SQS: delete_message(receipt_handle)
```

## 2. Dashboard Browsing — S3 Production (future)

Eager full-corpus scan is not viable against S3 (too slow, no tiktoken). Instead: the tree is built from a `ListObjectsV2` call; per-file stats (words, tokens, chunk count) come from OpenSearch metadata stored at ingest time. Chapter-name filtering stays client-side. Full-text content search goes to OpenSearch.

```mermaid
%%{init: {'theme': 'base', 'themeVariables': {'primaryColor': '#4f46e5', 'primaryTextColor': '#fff', 'primaryBorderColor': '#3730a3', 'secondaryColor': '#0891b2', 'secondaryTextColor': '#fff', 'tertiaryColor': '#059669', 'tertiaryTextColor': '#fff', 'lineColor': '#6b7280', 'textColor': '#111827', 'noteBkgColor': '#fef9c3', 'noteTextColor': '#713f12', 'activationBkgColor': '#e0e7ff', 'activationBorderColor': '#4f46e5', 'loopTextColor': '#4f46e5', 'labelBoxBkgColor': '#f0fdf4', 'labelBoxBorderColor': '#059669', 'labelTextColor': '#065f46'}}}%%
sequenceDiagram
    participant C as Browser
    participant F as Flask App
    participant S3 as S3
    participant OS as OpenSearch

    C->>F: GET /browse
    F->>S3: ListObjectsV2 prefix=uscis_policy_manual_clean/
    S3-->>F: all .md keys + sizes
    F->>F: group keys into volume->part->chapter tree
    F-->>C: html (full tree baked in + filter JS)

    Note over C: Chapter name filter, JS filters li elements client-side

    C->>F: GET /content/volume/part/chapter.md
    F->>S3: GetObject (key) — file content
    F->>OS: term query on s3_key, returns word count, token count, chunk count
    S3-->>F: .md content
    OS-->>F: file metadata
    F->>F: render markdown + merge metadata
    F-->>C: html fragment (rendered doc + badges)
    Note over C: JS injects fragment, same SPA pattern as local

    Note over C: User searches across all files
    C->>F: GET /search?q=asylum
    F->>OS: match query on text field, ranked results
    OS-->>F: [{s3_key, snippet, score}]
    F-->>C: JSON results
    Note over C: JS filters sidebar + renders result cards
```

## 3. Ask (Question Answering)

Titan request `dimensions` comes from the live OpenSearch mapping (`load_opensearch_vector_spec` in [`src/bedrock_utils.py`](../src/bedrock_utils.py)), same as ingest — not from env. `normalize: true` stays in code.

```mermaid
%%{init: {'theme': 'base', 'themeVariables': {'primaryColor': '#4f46e5', 'primaryTextColor': '#fff', 'primaryBorderColor': '#3730a3', 'secondaryColor': '#0891b2', 'secondaryTextColor': '#fff', 'tertiaryColor': '#059669', 'tertiaryTextColor': '#fff', 'lineColor': '#6b7280', 'textColor': '#111827', 'noteBkgColor': '#fef9c3', 'noteTextColor': '#713f12', 'activationBkgColor': '#e0e7ff', 'activationBorderColor': '#4f46e5', 'loopTextColor': '#4f46e5', 'labelBoxBkgColor': '#f0fdf4', 'labelBoxBorderColor': '#059669', 'labelTextColor': '#065f46'}}}%%
sequenceDiagram
    participant C as Client
    participant F as Flask App
    participant T as Titan Embedder
    participant OS as OpenSearch
    participant CL as Claude on Bedrock

    C->>F: POST /ask {question}

    F->>T: embed question (dimensions from prior GET _mapping)
    T-->>F: question vector

    F->>OS: knn search (question vector, k=5, innerproduct)
    OS-->>F: top-k chunks + source metadata

    F->>CL: prompt (question + chunks as context)
    CL-->>F: answer text

    F-->>C: {answer, answer_html, sources}
```
