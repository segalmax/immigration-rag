"""
JSONL test suite: keyword MRR/NDCG on OpenSearch top-k, optional Claude answer + Claude JSON judge.
Requires same env as /ask (AWS_REGION, OS_HOST, OS_INDEX, TITAN_EMBED_MODEL, CLAUDE_MODEL_ID, credentials).
"""
import argparse
import json
import math
import time
from pathlib import Path

import pydantic


class RetrievalEval(pydantic.BaseModel):
    mrr: float
    ndcg: float
    keywords_found: int
    total_keywords: int
    keyword_coverage: float


class AnswerEval(pydantic.BaseModel):
    feedback: str
    accuracy: float
    completeness: float
    relevance: float


class TestQuestion(pydantic.BaseModel):
    question: str
    keywords: list[str]
    reference_answer: str
    category: str


def default_tests_path() -> Path:
    return Path(__file__).resolve().parent / "tests.jsonl"


def _question_preview(question: str, max_len: int = 72) -> str:
    q = " ".join(question.split())
    if len(q) <= max_len:
        return q
    return q[: max_len - 1] + "…"


def load_tests(path: Path) -> list[TestQuestion]:
    tests = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            tests.append(TestQuestion.model_validate_json(line))
    return tests


def retrieve_chunks(question: str, k: int) -> list[dict]:
    import src.bedrock_utils
    vec = src.bedrock_utils.embed_text_for_titan(question)
    return src.bedrock_utils.knn_search_top_chunks(vec, k)


def calculate_mrr(keyword: str, retrieved_docs: list) -> float:
    keyword_lower = keyword.lower()
    for rank, doc in enumerate(retrieved_docs, start=1):
        blob = (doc.get("text") or "").lower()
        if keyword_lower in blob:
            return 1.0 / rank
    return 0.0


def calculate_dcg(relevances: list[int], k: int) -> float:
    dcg = 0.0
    for i in range(min(k, len(relevances))):
        dcg += relevances[i] / math.log2(i + 2)
    return dcg


def calculate_ndcg(keyword: str, retrieved_docs: list, k: int) -> float:
    keyword_lower = keyword.lower()
    relevances = [1 if keyword_lower in (doc.get("text") or "").lower() else 0 for doc in retrieved_docs[:k]]
    dcg = calculate_dcg(relevances, k)
    ideal = sorted(relevances, reverse=True)
    idcg = calculate_dcg(ideal, k)
    return dcg / idcg if idcg > 0 else 0.0


def _build_retrieval_eval(test: TestQuestion, retrieved_docs: list, k: int) -> RetrievalEval:
    n_kw = len(test.keywords)
    if n_kw == 0:
        return RetrievalEval(mrr=0.0, ndcg=0.0, keywords_found=0, total_keywords=0, keyword_coverage=0.0)
    mrr_scores = [calculate_mrr(kw, retrieved_docs) for kw in test.keywords]
    ndcg_scores = [calculate_ndcg(kw, retrieved_docs, k) for kw in test.keywords]
    avg_mrr = sum(mrr_scores) / n_kw
    avg_ndcg = sum(ndcg_scores) / n_kw
    keywords_found = sum(1 for s in mrr_scores if s > 0)
    return RetrievalEval(
        mrr=avg_mrr,
        ndcg=avg_ndcg,
        keywords_found=keywords_found,
        total_keywords=n_kw,
        keyword_coverage=100.0 * keywords_found / n_kw,
    )


def evaluate_retrieval(test: TestQuestion, k: int) -> RetrievalEval:
    chunks = retrieve_chunks(test.question, k)
    return _build_retrieval_eval(test, chunks, k)


def evaluate_retrieval_with_details(test: TestQuestion, k: int) -> tuple[RetrievalEval, list]:
    chunks = retrieve_chunks(test.question, k)
    return _build_retrieval_eval(test, chunks, k), chunks


def chunk_detail_fields(chunks: list[dict]) -> dict:
    return {
        "retrieved_titles": [c.get("section_path") or c.get("s3_key") or "" for c in chunks],
        "retrieved_doc_ids": [c.get("s3_key") or "" for c in chunks],
    }


def judge_answer_with_claude(test: TestQuestion, generated_answer: str) -> AnswerEval:
    import src.bedrock_utils
    user = (
        f"Question: {test.question}\n\n"
        f"Generated Answer:\n{generated_answer}\n\n"
        f"Reference Answer:\n{test.reference_answer}\n\n"
        "Evaluate the generated answer against the reference. "
        "Reply with ONE JSON object only (no markdown fences, no other text). Keys:\n"
        '"feedback" (string, concise), "accuracy" (number 1-5), '
        '"completeness" (number 1-5), "relevance" (number 1-5).'
    )
    body = json.dumps({
        "anthropic_version": "bedrock-2023-05-31",
        "max_tokens": 1024,
        "system": "You are an expert evaluator. Output a single JSON object only.",
        "messages": [{"role": "user", "content": user}],
    })
    out = src.bedrock_utils.invoke_claude(body)
    parts = out.get("content") or []
    if not parts:
        raise ValueError(f"judge response missing content: {out!r}")
    raw = (parts[0].get("text") or "").strip()
    return AnswerEval.model_validate_json(raw)


def evaluate_answer(test: TestQuestion, k: int, pause_before_judge_sec: float = 0.0) -> tuple[AnswerEval, str, list]:
    import src.bedrock_utils
    chunks = retrieve_chunks(test.question, k)
    if not chunks:
        raise LookupError(f"No chunks returned for question: {test.question!r}")
    generated = src.bedrock_utils.answer_question_with_claude(test.question, chunks)
    if pause_before_judge_sec > 0:
        time.sleep(pause_before_judge_sec)
    judged = judge_answer_with_claude(test, generated)
    return judged, generated, chunks


def evaluate_all_retrieval(tests_path: Path, limit: int | None, k: int, include_details: bool):
    tests = load_tests(tests_path)
    if limit is not None:
        tests = tests[:limit]
    total = len(tests)
    for i, test in enumerate(tests):
        progress = (i + 1) / total if total else 1.0
        if include_details:
            result, chunks = evaluate_retrieval_with_details(test, k)
            detail = {**chunk_detail_fields(chunks)}
        else:
            result = evaluate_retrieval(test, k)
            detail = None
        print(
            f"[retrieval {i + 1}/{total}] mrr={result.mrr:.4f} ndcg={result.ndcg:.4f} "
            f"cov={result.keyword_coverage:.1f}% | {test.category} | {_question_preview(test.question)}",
            flush=True,
        )
        if include_details:
            yield test, result, progress, detail
        else:
            yield test, result, progress


def evaluate_all_answers(tests_path: Path, limit: int | None, k: int, include_details: bool, bedrock_pause_sec: float = 0.0):
    tests = load_tests(tests_path)
    if limit is not None:
        tests = tests[:limit]
    total = len(tests)
    for i, test in enumerate(tests):
        progress = (i + 1) / total if total else 1.0
        print(
            f"[answer {i + 1}/{total}] start | {test.category} | {_question_preview(test.question)}",
            flush=True,
        )
        result, generated_answer, chunks = evaluate_answer(test, k, pause_before_judge_sec=bedrock_pause_sec)
        print(
            f"[answer {i + 1}/{total}] done acc={result.accuracy:.2f} comp={result.completeness:.2f} rel={result.relevance:.2f}",
            flush=True,
        )
        if include_details:
            details = {
                "generated_answer": generated_answer,
                "judge_feedback": result.feedback,
                **chunk_detail_fields(chunks),
            }
            yield test, result, progress, details
        else:
            yield test, result, progress
        if bedrock_pause_sec > 0 and i < total - 1:
            time.sleep(bedrock_pause_sec)


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="RAG eval: retrieval metrics and/or answer+judge (Bedrock).")
    p.add_argument("--tests", type=Path, default=None, help="tests.jsonl path (default: beside this file)")
    p.add_argument("--retrieval-only", action="store_true", help="Only MRR/NDCG/coverage")
    p.add_argument("--answer-only", action="store_true", help="Only generate+judge (still retrieves)")
    p.add_argument("--limit", type=int, default=None, help="Max tests to run")
    p.add_argument("--k", type=int, default=5, help="OpenSearch top-k")
    p.add_argument("--output-retrieval", type=Path, default=None, help="Write retrieval JSON summary")
    p.add_argument("--output-answer", type=Path, default=None, help="Write answer+judge JSON summary")
    p.add_argument("--details", action="store_true", help="Embed per-test detail dicts in JSON output")
    p.add_argument("--bedrock-pause-seconds", type=float, default=1.75, help="Sleep this long after each answer before judge, and between tests (0 disables; reduces 503 bursts)")
    return p.parse_args()


def _retrieval_row(test: TestQuestion, r: RetrievalEval, details: dict | None) -> dict:
    row = {
        "question": test.question,
        "category": test.category,
        "mrr": r.mrr,
        "ndcg": r.ndcg,
        "keywords_found": r.keywords_found,
        "total_keywords": r.total_keywords,
        "keyword_coverage": r.keyword_coverage,
    }
    if details is not None:
        row["details"] = details
    return row


def _answer_row(test: TestQuestion, r: AnswerEval, details: dict | None) -> dict:
    row = {
        "question": test.question,
        "category": test.category,
        "accuracy": r.accuracy,
        "completeness": r.completeness,
        "relevance": r.relevance,
        "feedback": r.feedback,
    }
    if details is not None:
        row["details"] = details
    return row


def main() -> None:
    import dotenv
    dotenv.load_dotenv(override=True)
    args = parse_args()
    tests_path = args.tests or default_tests_path()
    if not tests_path.is_file():
        raise FileNotFoundError(f"Tests file not found: {tests_path}")

    run_retrieval = not args.answer_only
    run_answers = not args.retrieval_only

    if run_retrieval:
        print("--- retrieval ---", flush=True)
        rows = []
        for item in evaluate_all_retrieval(tests_path, args.limit, args.k, args.details):
            if args.details:
                test, res, _prog, det = item
                rows.append(_retrieval_row(test, res, det))
            else:
                test, res, _prog = item
                rows.append(_retrieval_row(test, res, None))
        n = len(rows)
        if n:
            mean_mrr = sum(r["mrr"] for r in rows) / n
            mean_ndcg = sum(r["ndcg"] for r in rows) / n
            mean_cov = sum(r["keyword_coverage"] for r in rows) / n
            print(f"Retrieval ({n} tests): mean MRR={mean_mrr:.4f} mean NDCG={mean_ndcg:.4f} mean coverage%={mean_cov:.2f}")
        if args.output_retrieval:
            args.output_retrieval.write_text(json.dumps(rows, indent=2), encoding="utf-8")
            print(f"Wrote {args.output_retrieval}")

    if run_answers:
        print("--- answer + judge ---", flush=True)
        rows = []
        pause = max(0.0, args.bedrock_pause_seconds)
        for item in evaluate_all_answers(tests_path, args.limit, args.k, args.details, bedrock_pause_sec=pause):
            if args.details:
                test, res, _prog, det = item
                rows.append(_answer_row(test, res, det))
            else:
                test, res, _prog = item
                rows.append(_answer_row(test, res, None))
        n = len(rows)
        if n:
            mean_a = sum(r["accuracy"] for r in rows) / n
            mean_c = sum(r["completeness"] for r in rows) / n
            mean_r = sum(r["relevance"] for r in rows) / n
            print(f"Answers ({n} tests): mean accuracy={mean_a:.3f} completeness={mean_c:.3f} relevance={mean_r:.3f}")
        if args.output_answer:
            args.output_answer.write_text(json.dumps(rows, indent=2), encoding="utf-8")
            print(f"Wrote {args.output_answer}")


if __name__ == "__main__":
    main()
