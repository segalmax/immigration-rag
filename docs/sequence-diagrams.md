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

    C->>F: POST /v1/uploads/presign {filename, category, h1, h2, ...}
    Note over F: USCIS key = uscis_policy_manual_clean/{h1_slug}/{h2_slug}/{filename} (see app.py _s3_key_for)
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

    Note over W: No separate normalize step in current worker (clean corpus upstream via clean_kb.py)

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

## 2. Dashboard browsing (two modes in `app.py`)

**Local corpus** — routes `/`, `/browse`, `/content/*`, `/search`: read [`data/uscis_policy_manual_clean/`](../data/) via `load_corpus()` (in-memory `_cache`). Search is **substring scan** in Python over loaded file text, not OpenSearch.

**S3 mirror** — routes `/s3/`, `/s3/browse`, `/s3/content/*`, `/s3/search`: `load_s3_corpus()` does `ListObjectsV2` + **`GetObject` per `.md`** into a cached DataFrame (same in-memory search as local). **No OpenSearch** on these paths today.

```mermaid
%%{init: {'theme': 'base', 'themeVariables': {'primaryColor': '#4f46e5', 'primaryTextColor': '#fff', 'primaryBorderColor': '#3730a3', 'secondaryColor': '#0891b2', 'secondaryTextColor': '#fff', 'tertiaryColor': '#059669', 'tertiaryTextColor': '#fff', 'lineColor': '#6b7280', 'textColor': '#111827', 'noteBkgColor': '#fef9c3', 'noteTextColor': '#713f12', 'activationBkgColor': '#e0e7ff', 'activationBorderColor': '#4f46e5', 'loopTextColor': '#4f46e5', 'labelBoxBkgColor': '#f0fdf4', 'labelBoxBorderColor': '#059669', 'labelTextColor': '#065f46'}}}%%
sequenceDiagram
    participant C as Browser
    participant F as Flask App
    participant Disk as LocalCorpus
    participant S3 as S3

    Note over C,Disk: Local: /browse /content /search
    C->>F: GET /browse
    F->>Disk: load_corpus()
    Disk-->>F: tree + stats
    F-->>C: browse.html

    C->>F: GET /search?q=term
    F->>F: substring on cached clean files
    F-->>C: JSON

    Note over C,S3: S3 mirror: /s3/browse /s3/search
    C->>F: GET /s3/browse
    F->>S3: ListObjectsV2 + GetObject per .md
    S3-->>F: bodies cached in _s3_cache
    F-->>C: s3_browse.html
```

**Future / scale:** moving search and per-file stats to OpenSearch (or S3 Select, etc.) would avoid loading full corpus bodies into memory.

## 3. Ask (Question Answering)

Titan request `dimensions` comes from the live OpenSearch mapping (`load_opensearch_vector_spec` in [`src/bedrock_utils.py`](../src/bedrock_utils.py)), same as ingest — not from env. `normalize: true` stays in code. On **`POST /ask`**, Flask imports `src.bedrock_utils` and calls `run_ask` (Titan → k-NN `k=5` → Claude); **`GET /ask`** only renders `ask.html` (no Bedrock import).

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
