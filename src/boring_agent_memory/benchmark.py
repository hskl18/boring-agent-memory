from __future__ import annotations

import json
import shutil
import statistics
import tempfile
import time
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from .index import build_index
from .ingest import ingest_file, iter_candidate_files
from .privacy import SECRET_PATTERNS
from .query import QueryResult, query_memory


@dataclass(frozen=True)
class BenchmarkCase:
    id: str
    category: str
    query: str
    expected_source: str | None
    forbidden_sources: tuple[str, ...] = ()
    forbidden_terms: tuple[str, ...] = ()


def run_benchmark(
    corpus_dir: Path | str,
    cases_path: Path | str,
    limit: int = 3,
) -> dict[str, Any]:
    corpus_dir = Path(corpus_dir).expanduser().resolve()
    cases_path = Path(cases_path).expanduser().resolve()
    cases = load_benchmark_cases(cases_path)

    with tempfile.TemporaryDirectory() as tmp:
        workspace = (Path(tmp) / "corpus").resolve()
        shutil.copytree(corpus_dir, workspace)
        db_path = Path(tmp) / "memory.db"

        started = time.perf_counter()
        build = build_index(
            db_path=db_path,
            includes=[workspace.as_posix()],
            workspace=workspace,
            source_type="benchmark_fixture",
        )
        rebuild_ms = elapsed_ms(started)
        index_size_bytes = database_size(db_path)
        records = load_redacted_records(workspace)

        bm25 = evaluate_strategy(
            cases,
            workspace,
            lambda case: query_memory(
                db_path=db_path,
                query=case.query,
                limit=limit,
                source_type="benchmark_fixture",
                workspace=workspace,
            ),
        )
        exact_grep = evaluate_strategy(
            cases,
            workspace,
            lambda case: exact_phrase_grep(records, case.query, limit),
        )

    return {
        "schema_version": 1,
        "benchmark": "benchmark-v1",
        "corpus": {
            "documents": build["indexed"],
            "cases": len(cases),
            "category_counts": dict(sorted(Counter(case.category for case in cases).items())),
        },
        "index": {
            "rebuild_ms": rebuild_ms,
            "size_bytes": index_size_bytes,
        },
        "strategies": {
            "bm25": bm25,
            "exact_phrase_grep": exact_grep,
            "embeddings": {"status": "not_run", "reason": "optional provider-neutral baseline"},
            "hybrid": {"status": "not_run", "reason": "requires an embedding baseline"},
        },
    }


def load_benchmark_cases(path: Path) -> list[BenchmarkCase]:
    cases: list[BenchmarkCase] = []
    ids: set[str] = set()
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        payload = json.loads(line)
        case = BenchmarkCase(
            id=payload["id"],
            category=payload["category"],
            query=payload["query"],
            expected_source=payload.get("expected_source"),
            forbidden_sources=tuple(payload.get("forbidden_sources", ())),
            forbidden_terms=tuple(payload.get("forbidden_terms", ())),
        )
        if case.id in ids:
            raise ValueError(f"{path}:{line_number} duplicate case id {case.id}")
        ids.add(case.id)
        cases.append(case)
    if len(cases) < 100:
        raise ValueError(f"{path} must contain at least 100 cases")
    return cases


def load_redacted_records(workspace: Path) -> list[tuple[str, str]]:
    records: list[tuple[str, str]] = []
    for path in iter_candidate_files([workspace.as_posix()], workspace=workspace):
        record = ingest_file(path, workspace=workspace, source_type="benchmark_fixture")
        if record:
            records.append((record.source_path, f"{record.title}\n{record.content}"))
    return records


def exact_phrase_grep(
    records: list[tuple[str, str]], query: str, limit: int
) -> list[QueryResult]:
    needle = query.casefold().strip()
    if not needle:
        return []
    matches: list[QueryResult] = []
    for source_path, text in records:
        if needle not in text.casefold() and needle not in source_path.casefold():
            continue
        matches.append(
            QueryResult(
                id=source_path,
                source_type="benchmark_fixture",
                source_path=source_path,
                workspace=str(Path(source_path).parent),
                title=Path(source_path).name,
                score=0.0,
                snippet="[exact phrase match]",
                strategy="exact_phrase_grep",
            )
        )
    return matches[:limit]


def evaluate_strategy(
    cases: list[BenchmarkCase],
    workspace: Path,
    retrieve: Callable[[BenchmarkCase], list[QueryResult]],
) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    latencies: list[float] = []
    for case in cases:
        started = time.perf_counter()
        results = retrieve(case)
        latencies.append(elapsed_ms(started))
        rows.append(evaluate_case(case, results, workspace))

    positive = [row for row in rows if row["expected_source"] is not None]
    negative = [row for row in rows if row["expected_source"] is None]
    categories: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        categories[row["category"]].append(row)

    return {
        "status": "run",
        "metrics": summarize(positive, negative, rows),
        "latency_ms": {
            "median": round(statistics.median(latencies), 3),
            "p95": round(percentile(latencies, 0.95), 3),
        },
        "categories": {
            category: summarize(
                [row for row in category_rows if row["expected_source"] is not None],
                [row for row in category_rows if row["expected_source"] is None],
                category_rows,
            )
            for category, category_rows in sorted(categories.items())
        },
        "failures": [row for row in rows if not row["correct"]],
    }


def evaluate_case(
    case: BenchmarkCase, results: list[QueryResult], workspace: Path
) -> dict[str, Any]:
    relative_results = [relative_source(result.source_path, workspace) for result in results]
    expected = case.expected_source
    rank = relative_results.index(expected) + 1 if expected in relative_results else None
    no_answer_correct = expected is None and not results
    forbidden_ranks = [
        relative_results.index(source) + 1
        for source in case.forbidden_sources
        if source in relative_results
    ]
    forbidden_source_hit = any(rank is None or forbidden_rank <= rank for forbidden_rank in forbidden_ranks)
    privacy_leaks = count_privacy_leaks(results, case.forbidden_terms)
    correct = (
        (no_answer_correct if expected is None else rank is not None)
        and not forbidden_source_hit
        and privacy_leaks == 0
    )
    return {
        "id": case.id,
        "category": case.category,
        "query": case.query,
        "expected_source": expected,
        "top_source": relative_results[0] if relative_results else None,
        "rank": rank,
        "no_answer_correct": no_answer_correct,
        "forbidden_source_hit": forbidden_source_hit,
        "privacy_leak_count": privacy_leaks,
        "correct": correct,
    }


def summarize(
    positive: list[dict[str, Any]],
    negative: list[dict[str, Any]],
    rows: list[dict[str, Any]],
) -> dict[str, Any]:
    return {
        "cases": len(rows),
        "recall_at_1": ratio(sum(row["rank"] == 1 for row in positive), len(positive)),
        "recall_at_3": ratio(sum(row["rank"] is not None for row in positive), len(positive)),
        "mrr": ratio(sum(1 / row["rank"] for row in positive if row["rank"]), len(positive)),
        "source_accuracy": ratio(sum(row["rank"] == 1 for row in positive), len(positive)),
        "no_answer_precision": ratio(
            sum(row["no_answer_correct"] for row in negative), len(negative)
        ),
        "stale_conflict_accuracy": ratio(
            sum(row["correct"] for row in rows if row["category"] == "stale_conflict"),
            sum(row["category"] == "stale_conflict" for row in rows),
        ),
        "privacy_leak_count": sum(row["privacy_leak_count"] for row in rows),
    }


def count_privacy_leaks(results: list[QueryResult], forbidden_terms: tuple[str, ...]) -> int:
    leaks = 0
    for result in results:
        for pattern in SECRET_PATTERNS:
            leaks += sum(1 for match in pattern.finditer(result.snippet) if "[REDACTED]" not in match.group(0))
        leaks += sum(term.casefold() in result.snippet.casefold() for term in forbidden_terms)
    return leaks


def relative_source(source_path: str, workspace: Path) -> str:
    try:
        return Path(source_path).resolve().relative_to(workspace).as_posix()
    except ValueError:
        return source_path


def database_size(path: Path) -> int:
    return sum(candidate.stat().st_size for candidate in path.parent.glob(f"{path.name}*"))


def elapsed_ms(started: float) -> float:
    return round((time.perf_counter() - started) * 1000, 3)


def percentile(values: list[float], percentile_value: float) -> float:
    ordered = sorted(values)
    index = min(len(ordered) - 1, max(0, int(len(ordered) * percentile_value) - 1))
    return ordered[index]


def ratio(numerator: float, denominator: int) -> float:
    return round(numerator / denominator, 4) if denominator else 0.0
