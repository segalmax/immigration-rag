# Second project

This project is your chance to bring **Retrieval-Augmented Generation (RAG)** to life in a practical way. You'll build a Flask application that connects to AWS services like Bedrock, OpenSearch, and S3, and use Claude as your AI model. The best part is that you're free to choose **any topic you're passionate about**—from history, sports, or movies, to finance or healthcare—so the project feels like your own. Along the way, you'll also design a simple **UI/UX** layer for your app, because it's not just about making the backend work, but also about creating a product that's easy and enjoyable to use. For your dataset, you can grab free, ready-to-use material from **Kaggle**, which offers thousands of datasets to experiment with. The goal is to practice connecting the dots between data, AI, and user experience while learning how to deploy everything on AWS.

**Tech stack:**

- Flask API (Python 3.11+)
- Bedrock for:
  - Claude (chat/completions)
  - Titan Embeddings (text embeddings)
- OpenSearch **Serverless** as the vector store (k‑NN), configured via `opensearch/index_schema.json` + AWS APIs
- S3 for document drop‑box (students upload files here)
- SQS for event fan‑out from S3 to EC2 worker
- Textract (optional) to extract text from PDFs/images
- EC2 for app + worker (Gunicorn + systemd)

---

## 0) High‑Level Flow

```
[User uploads file] → S3 bucket → S3 Event → SQS Queue → EC2 Worker
EC2 Worker:
  - downloads object from S3
  - (optional) uses Textract to extract text
  - chunks → embeds (Titan) → indexes chunks into OpenSearch k‑NN index

User question → Flask /ask → retrieves top‑k chunks from OpenSearch →
  builds prompt → calls Claude via Bedrock → returns grounded answer
```

---

## 1) Minimal AWS Setup (one-time)

- S3: `rag-class-docs-<team>` bucket
- SQS: `rag-class-docs-queue-<team>`
- OpenSearch serverless
- IAM: EC2 role with Bedrock, S3, SQS, OpenSearch, Textract
- EC2: Ubuntu 22.04 with Python 3.11, Flask app + worker

---

## 2) Project Repo Structure

Generic class layout uses top-level `*_utils.py` files. **This repo** keeps shared code under `src/`:

```
app.py
worker.py
src/
  bedrock_utils.py   # Titan + Claude + OpenSearch vector spec + run_ask (RAG)
  opensearch_utils.py
  chunking.py
  s3_utils.py
requirements.txt
scripts/
opensearch/index_schema.json
systemd/
tests/
```

---

## 3) Environment Variables

```
PORT, AWS_REGION, S3_BUCKET, SQS_QUEUE_URL, OS_HOST, OS_INDEX, CLAUDE_MODEL_ID, TITAN_EMBED_MODEL
```

`OS_HOST` must be the OpenSearch Serverless **hostname only** (from `batch-get-collection` → `collectionEndpoint`, remove `https://`). Mismatched host yields **403** on index HTTP.

(Optional: `APP_RELOADER=0` to disable Flask reloader when debugging.)

---

## 4) Dependencies

See [`requirements.txt`](../requirements.txt). Includes `flask`, `boto3`, `requests`, `requests-aws4auth`, `python-dotenv`, `langchain-text-splitters`, `pandas`, `plotly`, `tiktoken`, `markdown`, and parsing libs for the corpus scripts. (No `opensearch-py` — HTTP to OpenSearch Serverless via `requests` + SigV4.)

---

## 5) Utilities

- `src/bedrock_utils.py` → Titan embed, Claude invoke, `load_opensearch_vector_spec`, `run_ask`
- `src/opensearch_utils.py` → SigV4 auth, index `_doc`, k-NN search HTTP
- `src/chunking.py` → LangChain splitters
- `src/s3_utils.py` → S3 download helper

---

## 6) Worker

Polls SQS, downloads S3 docs, extracts text (Textract optional), embeds + indexes.

---

## 7) Flask API

`/health`, dashboard and browse routes (local + `/s3/*` mirror), upload presign, **`/ask`** (POST JSON question → `src.bedrock_utils.run_ask`).

---

## 8) Scripts

- `scripts/create_index.py`, `scripts/check_aws.py`, `scripts/smoke_test.py`, plus corpus pipeline scripts (`parse_uscis.py`, `clean_kb.py`, `analyze_kb.py`, etc.)

---

## 9) Run

Install deps, set env, run worker + app, test with curl.

---

## 10) Systemd

`rag-api.service`, `rag-worker@.service` (instances `@1`–`@3`)

---

## 11) S3 → SQS Wiring

Event notification `ObjectCreated` → SQS.

---

## 12) Optional AI Services

Comprehend, Translate, Polly.

---

## 13) Evaluation Rubric

Bootstraps, indexing works, OpenSearch works, Claude answers grounded, optional extra service.

---

## 14) Troubleshooting

IAM, dimension mismatch, SQS body, Textract throttling, connectivity.

---

## 15) Stretch Goals

Reranking, feedback loop, deduping, caching, batch embedding.
