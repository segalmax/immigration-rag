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
- Number steps (`1`, `2`, `3.a`, `3.b` for parallel). Meaningful shapes (cylinder=DB, hexagon=queue, diamond=decision).
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
- `kb_dashboard/` = local dev tool only, not the production API.
- **Two upload tracks:** USCIS (category=uscis, S3 key from H1/H2 headers, rich metadata) · Other (category=other, flat `uploads/` prefix, minimal metadata).
- **SQS trigger:** client calls `POST /v1/uploads/notify` after S3 PUT — not an S3 event notification.
- **Chunking:** `MarkdownHeaderTextSplitter` first (section_path metadata per chunk) → `RecursiveCharacterTextSplitter` only for chunks >2000 chars.
- **OpenSearch chunk fields:** `s3_key`, `category`, `volume`, `part`, `chapter`, `source_url`, `section_path[]`, `text`, `chunk_index`, `vector`.
- **S3 CORS:** must `put_bucket_cors` (AllowedMethods: PUT/GET/HEAD, AllowedOrigins: *) before browser presigned-URL uploads work.

---

## Codebase Overview

RAG pipeline on USCIS Policy Manual (446 clean `.md` files). Two apps: `kb_dashboard/` (local dev inspector, fully working) and `app.py` (production API, skeleton). Ingestion worker and query route not yet implemented.

**Stack**: Flask · Tailwind CDN · Tabulator.js · Plotly · Bedrock (Titan + Claude) · OpenSearch Serverless · S3 · SQS · EC2 · systemd

**Structure**: `scripts/` → data pipeline · `src/` → production modules (stubs) · `kb_dashboard/` → local dev tool · `opensearch/` → index schema · `systemd/` → EC2 service configs

For detailed architecture, see [docs/CODEBASE_MAP.md](docs/CODEBASE_MAP.md).

---

## Open Issues
- **Footnote gap:** `clean_kb.py` misses `[^ n]` / bare `[n]` — 4 files still noisy. Awaiting fix instruction.
- **Token counts approximate:** `tiktoken cl100k_base` ≠ Titan tokenizer. Good enough proxy for now.
- **Hardcoded paths** in `kb_dashboard/app.py` — must switch to env vars before EC2 deploy.
- **OpenSearch index** needs recreating with new schema before first worker run (`python scripts/create_index.py`).
