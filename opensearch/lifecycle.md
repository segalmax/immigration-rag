# OpenSearch Collection Lifecycle

```mermaid
flowchart TD
    A([Start of day]) --> B["--up --col immig-col3"]
    B --> B1["creates collection + policies<br/>waits ~5 min for ACTIVE<br/>creates kb_index"]
    B1 --> C{backup file<br/>exists?}
    C -- yes --> D["bulk re-indexes docs<br/>from data/opensearch_dump_immig-col3.jsonl"]
    C -- no --> E
    D --> E([Work / ingest / query])
    E --> F([End of day])
    F --> G["--down --all"]
    G --> G1["saves mapping + policies<br/>scrolls all docs<br/>deletes collection"]
    G1 --> H[(data/opensearch_config_immig-col3.json<br/>data/opensearch_dump_immig-col3.jsonl)]
    H --> A

    style G fill:#27ae60,color:#fff
    style B fill:#27ae60,color:#fff
    style H fill:#2980b9,color:#fff
    style B1 fill:#f0f0f0
    style G1 fill:#f0f0f0
```

## Commands

| Command | What it does |
|---|---|
| `python opensearch/manage.py --up --col immig-col3` | Provision collection + auto-restore if backup exists |
| `python opensearch/manage.py --down --all` | Backup all docs + delete all collections |
| `python opensearch/manage.py --backup --col immig-col3` | Backup only, no delete |
| `python opensearch/manage.py --restore --col immig-col3` | Restore docs into existing collection |

## Files

```
opensearch/
  manage.py        # this script
  lifecycle.md     # this file
  data/
    opensearch_config_<col>.json   # index mapping + policies (committed)
    opensearch_dump_<col>.jsonl    # doc backup (gitignored if large)
```
