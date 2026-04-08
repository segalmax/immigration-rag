# Deployment Diagram

**What this shows:** where each process runs and which AWS APIs it calls.
For step-by-step request flows, see [sequence-diagrams.md](sequence-diagrams.md).

---

## 1 — EC2 Runtime Structure

Who runs what and how processes are wired together.

```mermaid
%%{ init: { 'theme': 'base' } }%%
flowchart TD
    classDef actor   fill:#dbeafe,stroke:#3b82f6,color:#1e3a5f
    classDef service fill:#dcfce7,stroke:#16a34a,color:#14532d
    classDef worker  fill:#fef9c3,stroke:#ca8a04,color:#713f12
    classDef infra   fill:#fce7f3,stroke:#db2777,color:#500724

    Browser(["Browser"]):::actor

    subgraph ec2 ["EC2 Instance"]
        subgraph rag_api ["systemd: rag-api"]
            nginx["nginx :80/:443"]:::infra
            gunicorn["gunicorn :5000"]:::infra
            flask["Flask app.py"]:::service
            nginx -->|"proxy_pass"| gunicorn
            gunicorn -->|"WSGI"| flask
        end
        subgraph rag_worker ["systemd: rag-worker"]
            worker["worker.py"]:::worker
        end
    end

    Browser -->|"HTTPS"| nginx
```

## 2 — AWS Service Calls

Which process calls which AWS API, and why.

| Process | AWS Service | Call | Purpose |
|---------|-------------|------|---------|
| Flask | S3 | `GeneratePresignedUrl` / `GetObject` | Upload UI + S3 browse |
| Flask | Bedrock Titan | `InvokeModel` | Embed the user's question |
| Flask | OpenSearch | `kNN search` | Retrieve top-k relevant chunks |
| Flask | Bedrock Claude | `InvokeModel` | Generate grounded answer |
| worker | SQS | `ReceiveMessage` / `DeleteMessage` | Poll for new file events |
| worker | S3 | `GetObject` | Download the uploaded `.md` file |
| worker | Bedrock Titan | `InvokeModel` | Embed each chunk |
| worker | OpenSearch | `bulk _doc` | Index chunks into k-NN index |
| S3 (auto) | → SQS | `ObjectCreated` event | Trigger worker after browser upload |

## 3 — Ingest Chain (one-time data load)

```mermaid
%%{ init: { 'theme': 'base' } }%%
flowchart LR
    classDef storage fill:#ede9fe,stroke:#7c3aed,color:#2e1065
    classDef service fill:#dcfce7,stroke:#16a34a,color:#14532d
    classDef worker  fill:#fef9c3,stroke:#ca8a04,color:#713f12

    script["scripts/upload_uscis.py\n(446 .md files)"]:::service
    S3["S3"]:::storage
    SQS["SQS"]:::storage
    worker["worker.py"]:::worker
    OS["OpenSearch Serverless"]:::storage

    script -->|"PUT"| S3
    S3 -->|"ObjectCreated event"| SQS
    SQS -->|"ReceiveMessage"| worker
    worker -->|"embed + bulk index"| OS
```

---

## Data Load Path (one-time)

Run from any machine with AWS creds (or the EC2 instance itself):

```
python scripts/upload_uscis.py        # 446 clean .md → S3
                                      # each PUT fires ObjectCreated → SQS
                                      # worker picks up → chunk → embed → index
```

The ingest pipeline is identical to the browser upload flow — no separate tool needed.

---

## systemd — key notes

**What it does:** starts gunicorn + worker at EC2 boot, restarts on crash, injects `.env` vars, logs via `journalctl`.

```bash
journalctl -u rag-api -f      # tail Flask/gunicorn logs
journalctl -u rag-worker -f   # tail worker logs
```

**`rag-api.service` critical lines:**

| Line | Why |
|------|-----|
| `EnvironmentFile=.../.env` | All `os.environ["..."]` in app.py/src/ read from here. Missing var → KeyError crash. |
| `gunicorn app:app --bind 0.0.0.0:5000 --workers 2` | Replaces `python app.py`. 2 parallel Flask processes, each serves 1 request at a time. `app:app` = "the `app` object in `app.py`". |
| `Restart=always` | Auto-relaunch after crash, 5s delay. |

**`rag-worker.service` critical lines:**

| Line | Why |
|------|-----|
| `python worker.py` | No gunicorn — worker is an infinite SQS poll loop, not a web server. |
| `Restart=always` | If one bad message crashes the worker, the queue silently stops draining without this. |
