# Evaluation pipeline — sequence

Offline eval ([`eval.py`](eval.py)) uses the same AWS/OpenSearch configuration as Flask `/ask` (`AWS_REGION`, `OS_HOST`, `OS_INDEX`, `TITAN_EMBED_MODEL`, `CLAUDE_MODEL_ID`, default credential chain for Bedrock and SigV4 to OpenSearch Serverless).

**CLI modes**

- Default: run **retrieval** metrics (MRR, NDCG, keyword coverage) then **answer + judge** (Claude generates, Claude scores JSON vs `reference_answer`).
- `--retrieval-only`: skip generation and judge.
- `--answer-only`: skip the retrieval aggregate pass (each answer path still embeds + k-NN retrieves).

**Per-chunk fields** (from OpenSearch `_source`): `text`, `s3_key`, `section_path`, `source_url`, `volume`, `part`, `chapter`, `category`, `score`. Keyword metrics substring-match on `text` only. Detail JSON uses `section_path` or `s3_key` as title-like labels.

```mermaid
sequenceDiagram
  autonumber
  participant Op as Operator
  participant Ev as evaluation_eval_py
  participant BU as src_bedrock_utils
  participant OSu as src_opensearch_utils
  participant AOSS as OpenSearch_Serverless
  participant BR as Bedrock_Runtime

  Op->>Ev: python -m evaluation.eval (flags)
  Ev->>Ev: parse_args()
  Ev->>Ev: load_tests(tests_jsonl_path)
  Note over Ev,BU: First Titan embed triggers vector spec load (once per process)

  loop Each TestQuestion (respect --limit)
    Ev->>BU: embed_text_for_titan(question)
    alt Vector spec not cached
      BU->>BU: load_opensearch_vector_spec(OS_ENDPOINT, OS_INDEX, OPENSEARCH_HTTP_AUTH)
      BU->>AOSS: HTTP GET /OS_INDEX/_mapping
      AOSS-->>BU: knn_vector field dimension, space_type innerproduct
      BU->>BU: cache dimension validate vs Titan body
    end
    BU->>BR: invoke_model(modelId=TITAN_EMBED_MODEL, inputText=question, dimensions, normalize)
    BR-->>BU: embedding vector
    BU-->>Ev: list[float]

    Ev->>BU: knn_search_top_chunks(query_vector, k, category_filter?)
    BU->>OSu: build POST _search payload (knn on vector field, optional term filter category)
    OSu->>AOSS: HTTP POST /OS_INDEX/_search (SigV4 aoss)
    AOSS-->>OSu: hits _source text s3_key section_path scores
    OSu-->>BU: list of chunk dicts
    BU-->>Ev: chunks

    Ev->>Ev: For each keyword substring match in chunk text compute MRR NDCG coverage

    opt Answer and judge mode (not retrieval-only)
      Ev->>BU: answer_question_with_claude(question, chunks)
      BU->>BU: format CONTEXT blocks from chunk metadata and text
      BU->>BR: invoke_model(CLAUDE_MODEL_ID, anthropic_version, system+user messages)
      BR-->>BU: content[0].text (answer markdown)
      BU-->>Ev: generated_answer string

      Ev->>Ev: Build judge prompt (question, generated_answer, reference_answer) require JSON only
      Ev->>BU: invoke_claude(judge_request_json_body)
      BU->>BR: invoke_model(CLAUDE_MODEL_ID, judge messages)
      BR-->>BU: assistant text (must be JSON object)
      BU-->>Ev: raw judge text
      Ev->>Ev: pydantic model_validate_json AnswerEval or raise
    end
  end

  opt CLI writes artifacts
    Ev->>Ev: Write paths from --output-retrieval / --output-answer
  end
  Ev-->>Op: Printed aggregates per suite
```
