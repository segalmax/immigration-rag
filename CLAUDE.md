---
description: 
alwaysApply: true
---

# CLAUDE.md — Session Rules & Project Memory

---

## Shorthand
- **wtrw** = "what's the right word/phrase?" — give the industry-standard term, don't just use the user's word.
- **amq** = "ask me all the right questions" — before planning/implementing, ask every question needed to avoid wrong assumptions, and to prevent bad practices.

## Behavior
- Push back, ask questions, object when something is wrong. Senior dev colleague, not yes-man.
- Be short. Restate the query before answering. Say "I don't know" if unsure.
- Flag approximations explicitly — never silently use stand-ins.
- Step-by-step: do exactly what's asked, no more.
- Plan before changes touching multiple files.
- **Update this file** whenever a new preference is learned.

---

## Code Strategy
- **Fail fast** — no `try/except: pass`, no fallbacks, no defensive defaults. Let it crash loudly.
- **Off-the-shelf first** — always search for a library before writing regex/parsing logic manually.
- **Minimal code** — delete aggressively. Simple lean code is king.
- **Top-down readable** — extract named functions so code reads like prose without drowning in details.
- **Imports:** always `import module` then `module.Class()` — never `from module import X`. Shows origin clearly.
- **Function signatures:** one line when possible — `def foo(a: str, b: int, c: list) -> dict:`
- **argparse:** always wrap in `def parse_args()`, use dest var names matching the arg name, one-line `add_argument` calls. Never `sys.argv`.

---

## UI / Tech
- Flask (instructor-required) + Tailwind CDN + Plotly (server-side) + Tabulator.js + `markdown` lib.
- No npm, no webpack, no build steps. CDN only.
- Pandas for data wrangling. Jinja2 server-side rendering.

---

## Diagrams
- Mermaid preferred. Nest sub-components in parent boundaries.
- Number steps (`1`, `2`, `3.a`, `3.b` for parallel). Meaningful best conventional shapes.
- Consistent colors per category. Generous spacing, no crossing arrows.

---

## Teaching Style (when asked)
- Top-down: big picture first, then details.
- Mermaid diagrams, tables for comparisons.
- Ground in real code (actual file paths + names). Max ~20 lines of explanation.
- Analogies to Python/Django/MySQL when applicable.

---

## Project Context
- **Educational AWS class project** — instructor requires Flask.
- **Goal:** RAG app — USCIS Policy Manual → S3 → SQS → EC2 worker → OpenSearch (k-NN) → Claude via Bedrock.
- **Corpus:** `uscis_policy_manual/` (raw 494) · `uscis_policy_manual_clean/` (clean 446).
- `app.py` serves the KB dashboard, uploads, and **`/ask`** (RAG: Titan embed → OpenSearch k-NN → Claude). **`src.bedrock_utils` is imported only on `POST /ask`** (GET serves `ask.html` without Bedrock/OpenSearch). Titan `dimensions` matches the live index: [`src/bedrock_utils.py`](src/bedrock_utils.py) loads it from `GET /_mapping` once per process (`load_opensearch_vector_spec`), not from env or a hardcoded size.
- **`/ask` answers:** [`src/bedrock_utils.py`](src/bedrock_utils.py) (`run_ask`) system prompt is **retrieval-grounded only** — refuse when context is insufficient or confidence is low; do not answer from general model knowledge.
- **Two upload tracks:** USCIS (category=uscis, S3 key from H1/H2 headers, rich metadata) · Other (category=other, flat `uploads/` prefix, minimal metadata).
- **SQS trigger:** S3 `ObjectCreated` event sends the uploaded object to SQS after browser PUT completes.
- **Chunking:** `MarkdownHeaderTextSplitter` first (section_path metadata per chunk) → `RecursiveCharacterTextSplitter` only for chunks >2000 chars.
- **OpenSearch chunk fields (ingest):** [`worker.py`](worker.py) `build_doc` sends `s3_key`, `category`, `volume`, `part`, `chapter`, `source_url`, `section_path`, `text`, `chunk_index`, `vector` (indexed via **POST** `/_doc` per chunk in [`src/opensearch_utils.py`](src/opensearch_utils.py)). [`opensearch/index_schema.json`](opensearch/index_schema.json) also lists `chunk_id` / `doc_id` / `source_s3_key` — worker does **not** set those today; align or ignore until needed.
- **S3 CORS:** must `put_bucket_cors` (AllowedMethods: PUT/GET/HEAD, AllowedOrigins: *) before browser presigned-URL uploads work.

---

## Codebase Overview

RAG pipeline on USCIS Policy Manual (446 clean `.md` files). `app.py` is the main Flask app (including `POST /ask`), and `worker.py` is the ingestion worker. Titan/OpenSearch vector spec + `/ask` RAG live in [`src/bedrock_utils.py`](src/bedrock_utils.py). Other AWS helpers: [`src/chunking.py`](src/chunking.py), [`src/s3_utils.py`](src/s3_utils.py), [`src/opensearch_utils.py`](src/opensearch_utils.py).

**Stack**: Flask · Tailwind CDN · Tabulator.js · Plotly · Bedrock (Titan + Claude) · OpenSearch Serverless · S3 · SQS · EC2 · systemd

**Structure**: `scripts/` → one-off data tools · `app.py` + `worker.py` → main runtimes · `src/` → shared chunk + AWS clients · `kb_dashboard/templates/` → Flask templates · `opensearch/` → index schema · `systemd/` → `rag-api.service` (gunicorn **`--workers 1`** — one in-memory `_s3_cache`) + `rag-worker@.service` (3 instances on EC2)

For detailed architecture, see [docs/CODEBASE_MAP.md](docs/CODEBASE_MAP.md).

---

## Open Issues
- **Footnote gap:** `clean_kb.py` misses `[^ n]` / bare `[n]` — 4 files still noisy. Awaiting fix instruction.
- **Token counts approximate:** `tiktoken cl100k_base` ≠ Titan tokenizer. Good enough proxy for now.
- **Local corpus paths** in `app.py` — under repo `data/`; if missing on EC2, `/` is empty-state + banner (use `/s3/` or rsync `data/`). Env-based roots only if you mount corpus elsewhere.
- **`PORT` env** — `app.py` requires `os.environ["PORT"]` (no default); set in `.env` or shell.
- **OpenSearch index** needs recreating with new schema before first worker run (`python scripts/create_index.py`).
