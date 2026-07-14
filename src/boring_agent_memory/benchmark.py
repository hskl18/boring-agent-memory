from __future__ import annotations

import json
import hashlib
import shutil
import statistics
import tempfile
import time
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from .embeddings import (
    DenseIndex,
    EmbeddingAdapter,
    load_embedding_documents,
    reciprocal_rank_fusion,
)
from .index import build_index
from .ingest import IngestedRecord, ingest_file, iter_candidate_files
from .privacy import SECRET_PATTERNS
from .query import QueryResult, query_memory
from .schema import connect, init_db


@dataclass(frozen=True)
class BenchmarkCase:
    id: str
    category: str
    query: str
    expected_source: str | None
    expected_heading: str | None = None
    expected_start_line: int | None = None
    expected_end_line: int | None = None
    forbidden_sources: tuple[str, ...] = ()
    forbidden_terms: tuple[str, ...] = ()


def run_benchmark(
    corpus_dir: Path | str,
    cases_path: Path | str,
    limit: int = 3,
    benchmark_name: str = "benchmark-v2",
    chunk_size: int = 1600,
    embedding_adapter: EmbeddingAdapter | None = None,
) -> dict[str, Any]:
    corpus_dir = Path(corpus_dir).expanduser().resolve()
    cases_path = Path(cases_path).expanduser().resolve()
    cases = load_benchmark_cases(cases_path)
    identity_namespace = f"benchmark:{benchmark_name}"

    with tempfile.TemporaryDirectory() as tmp:
        workspace = (Path(tmp) / "corpus").resolve()
        shutil.copytree(corpus_dir, workspace)
        whole_db = Path(tmp) / "whole.db"
        chunked_db = Path(tmp) / "chunked.db"

        whole_index = build_benchmark_index(
            whole_db,
            workspace,
            chunk_size=0,
            identity_namespace=identity_namespace,
        )
        chunked_index = build_benchmark_index(
            chunked_db,
            workspace,
            chunk_size=chunk_size,
            identity_namespace=identity_namespace,
        )
        records = load_redacted_records(workspace, identity_namespace)

        whole_bm25 = evaluate_strategy(
            cases,
            workspace,
            lambda case: query_memory(
                whole_db,
                case.query,
                limit=limit,
                source_type="benchmark_fixture",
                workspace=workspace,
            ),
        )
        whole_bm25["index"] = whole_index
        def chunked_retrieve(case: BenchmarkCase) -> list[QueryResult]:
            return query_memory(
                chunked_db,
                case.query,
                limit=limit,
                source_type="benchmark_fixture",
                workspace=workspace,
            )

        chunked_bm25 = evaluate_strategy(cases, workspace, chunked_retrieve)
        chunked_bm25["index"] = chunked_index
        exact_grep = evaluate_strategy(
            cases,
            workspace,
            lambda case: exact_phrase_grep(records, case.query, limit),
        )

        if embedding_adapter is None:
            dense: dict[str, Any] = {
                "status": "not_run",
                "reason": "no explicit local embedding adapter was provided",
            }
            hybrid: dict[str, Any] = {
                "status": "not_run",
                "reason": "hybrid retrieval requires an explicit local embedding adapter",
            }
        else:
            candidate_depth = max(50, limit * 10)
            dense_started = time.perf_counter()
            dense_index = DenseIndex.build(
                embedding_adapter,
                load_embedding_documents(
                    chunked_db,
                    source_type="benchmark_fixture",
                    workspace=workspace,
                ),
            )
            dense_build_ms = elapsed_ms(dense_started)
            dense = evaluate_strategy(
                cases,
                workspace,
                lambda case: dense_index.query(case.query, limit=limit),
            )
            dense["index"] = {
                "build_ms": dense_build_ms,
                "vectors": len(dense_index.vectors),
                "dimensions": len(dense_index.vectors[0]) if dense_index.vectors else 0,
                "size_bytes_estimate": sum(
                    len(vector) * 8 for vector in dense_index.vectors
                ),
                "model_id": embedding_adapter.model_id,
                "model_revision": getattr(embedding_adapter, "model_revision", None),
                "model_license": getattr(embedding_adapter, "model_license", None),
                "model_source": (
                    "explicit_download"
                    if bool(getattr(embedding_adapter, "allow_download", False))
                    else "local_path"
                ),
                "text_leaves_machine": False,
                "download_allowed": bool(
                    getattr(embedding_adapter, "allow_download", False)
                ),
            }
            hybrid = evaluate_strategy(
                cases,
                workspace,
                lambda case: reciprocal_rank_fusion(
                    query_memory(
                        chunked_db,
                        case.query,
                        limit=candidate_depth,
                        source_type="benchmark_fixture",
                        workspace=workspace,
                    ),
                    dense_index.query(case.query, limit=candidate_depth),
                    limit=limit,
                ),
            )
            hybrid["parameters"] = {
                "fusion": "weighted_rrf",
                "lexical_weight": 0.6,
                "dense_weight": 0.4,
                "rrf_k": 60,
                "lexical_candidate_depth": candidate_depth,
                "dense_candidate_depth": candidate_depth,
            }

    return {
        "schema_version": 2,
        "benchmark": benchmark_name,
        "corpus": {
            "documents": whole_index["documents"],
            "cases": len(cases),
            "category_counts": dict(
                sorted(Counter(case.category for case in cases).items())
            ),
            "corpus_sha256": directory_hash(corpus_dir),
            "cases_sha256": file_hash(cases_path),
        },
        "strategies": {
            "whole_document_bm25": whole_bm25,
            "chunked_bm25": chunked_bm25,
            "exact_phrase_grep": exact_grep,
            "dense": dense,
            "hybrid_rrf": hybrid,
        },
    }


def build_benchmark_index(
    db_path: Path,
    workspace: Path,
    chunk_size: int,
    identity_namespace: str,
) -> dict[str, Any]:
    started = time.perf_counter()
    build = build_index(
        db_path=db_path,
        includes=[workspace.as_posix()],
        workspace=workspace,
        source_type="benchmark_fixture",
        chunk_size=chunk_size,
        identity_namespace=identity_namespace,
    )
    build_ms = elapsed_ms(started)
    conn = connect(db_path)
    init_db(conn)
    metadata = conn.execute(
        "SELECT config_json FROM index_metadata WHERE singleton = 1"
    ).fetchone()
    conn.close()
    portable_config = json.loads(metadata["config_json"])
    portable_config["workspace"] = "<BENCHMARK_CORPUS>"
    portable_config["includes"] = ["<BENCHMARK_CORPUS>"]
    portable_rendered = json.dumps(
        portable_config,
        sort_keys=True,
        separators=(",", ":"),
    )
    return {
        "build_ms": build_ms,
        "size_bytes": database_size(db_path),
        "documents": build["indexed"],
        "chunks": build["chunks"],
        "config_fingerprint": hashlib.sha256(portable_rendered.encode("utf-8")).hexdigest(),
        "config": portable_config,
        "chunk_size": chunk_size,
    }


def load_benchmark_cases(path: Path) -> list[BenchmarkCase]:
    cases: list[BenchmarkCase] = []
    ids: set[str] = set()
    for line_number, line in enumerate(
        path.read_text(encoding="utf-8").splitlines(), start=1
    ):
        if not line.strip():
            continue
        payload = json.loads(line)
        case = BenchmarkCase(
            id=payload["id"],
            category=payload["category"],
            query=payload["query"],
            expected_source=payload.get("expected_source"),
            expected_heading=payload.get("expected_heading"),
            expected_start_line=payload.get("expected_start_line"),
            expected_end_line=payload.get("expected_end_line"),
            forbidden_sources=tuple(payload.get("forbidden_sources", ())),
            forbidden_terms=tuple(payload.get("forbidden_terms", ())),
        )
        if case.id in ids:
            raise ValueError(f"{path}:{line_number} duplicate case id {case.id}")
        ids.add(case.id)
        cases.append(case)
    if not cases:
        raise ValueError(f"{path} does not contain any cases")
    return cases


def load_redacted_records(
    workspace: Path,
    identity_namespace: str,
) -> list[IngestedRecord]:
    records: list[IngestedRecord] = []
    for path in iter_candidate_files([workspace.as_posix()], workspace=workspace):
        record = ingest_file(
            path,
            workspace=workspace,
            source_type="benchmark_fixture",
            identity_namespace=identity_namespace,
        )
        if record:
            records.append(record)
    return records


def exact_phrase_grep(
    records: list[IngestedRecord], query: str, limit: int
) -> list[QueryResult]:
    needle = query.casefold().strip()
    if not needle:
        return []
    matches: list[QueryResult] = []
    for record in records:
        text = f"{record.title}\n{record.content}"
        if needle not in text.casefold() and needle not in record.source_path.casefold():
            continue
        result_id = hashlib.sha256(
            f"{record.id}\0exact_phrase_grep\0{record.content_hash}".encode("utf-8")
        ).hexdigest()
        matches.append(
            QueryResult(
                id=record.id,
                chunk_id=result_id,
                source_type="benchmark_fixture",
                source_path=record.source_path,
                workspace=record.workspace,
                title=record.title,
                heading="",
                start_line=1,
                end_line=max(1, len(text.splitlines())),
                citation=(
                    f"{record.source_path}:L1-L{max(1, len(text.splitlines()))}"
                ),
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
        "cases": rows,
        "failures": [row for row in rows if not row["correct"]],
    }


def evaluate_case(
    case: BenchmarkCase, results: list[QueryResult], workspace: Path
) -> dict[str, Any]:
    relative_results = [relative_source(result.source_path, workspace) for result in results]
    expected = case.expected_source
    rank = relative_results.index(expected) + 1 if expected in relative_results else None
    evidence_rank = None
    if expected is not None:
        for index, result in enumerate(results, start=1):
            if relative_source(result.source_path, workspace) != expected:
                continue
            heading_matches = (
                case.expected_heading is None or result.heading == case.expected_heading
            )
            start_matches = (
                case.expected_start_line is None
                or result.start_line == case.expected_start_line
            )
            end_matches = (
                case.expected_end_line is None or result.end_line == case.expected_end_line
            )
            if heading_matches and start_matches and end_matches:
                evidence_rank = index
                break
    no_answer_correct = expected is None and not results
    forbidden_ranks = [
        relative_results.index(source) + 1
        for source in case.forbidden_sources
        if source in relative_results
    ]
    forbidden_source_hit = any(
        rank is None or forbidden_rank <= rank for forbidden_rank in forbidden_ranks
    )
    privacy_leaks = count_privacy_leaks(results, case.forbidden_terms)
    expected_found = no_answer_correct if expected is None else evidence_rank is not None
    correct = expected_found and not forbidden_source_hit and privacy_leaks == 0
    return {
        "id": case.id,
        "category": case.category,
        "query": case.query,
        "expected_source": expected,
        "expected_heading": case.expected_heading,
        "expected_start_line": case.expected_start_line,
        "expected_end_line": case.expected_end_line,
        "top_source": relative_results[0] if relative_results else None,
        "rank": rank,
        "evidence_rank": evidence_rank,
        "no_answer_correct": no_answer_correct,
        "forbidden_source_hit": forbidden_source_hit,
        "privacy_leak_count": privacy_leaks,
        "correct": correct,
        "results": [
            {
                "source": relative_source(result.source_path, workspace),
                "chunk_id": result.chunk_id,
                "heading": result.heading,
                "start_line": result.start_line,
                "end_line": result.end_line,
                "citation": relative_citation(result, workspace),
            }
            for result in results
        ],
    }


def summarize(
    positive: list[dict[str, Any]],
    negative: list[dict[str, Any]],
    rows: list[dict[str, Any]],
) -> dict[str, Any]:
    return {
        "cases": len(rows),
        "recall_at_1": ratio(sum(row["rank"] == 1 for row in positive), len(positive)),
        "recall_at_3": ratio(
            sum(row["rank"] is not None and row["rank"] <= 3 for row in positive),
            len(positive),
        ),
        "evidence_recall_at_1": ratio(
            sum(row["evidence_rank"] == 1 for row in positive), len(positive)
        ),
        "evidence_recall_at_3": ratio(
            sum(
                row["evidence_rank"] is not None and row["evidence_rank"] <= 3
                for row in positive
            ),
            len(positive),
        ),
        "mrr": ratio(
            sum(1 / row["rank"] for row in positive if row["rank"]), len(positive)
        ),
        "source_accuracy": ratio(
            sum(row["rank"] == 1 for row in positive), len(positive)
        ),
        "no_answer_precision": ratio(
            sum(row["no_answer_correct"] for row in negative), len(negative)
        ),
        "stale_conflict_accuracy": ratio(
            sum(
                row["rank"] is not None
                and not row["forbidden_source_hit"]
                and row["privacy_leak_count"] == 0
                for row in rows
                if row["category"] == "stale_conflict"
            ),
            sum(row["category"] == "stale_conflict" for row in rows),
        ),
        "privacy_leak_count": sum(row["privacy_leak_count"] for row in rows),
    }


def count_privacy_leaks(results: list[QueryResult], forbidden_terms: tuple[str, ...]) -> int:
    leaks = 0
    for result in results:
        for pattern in SECRET_PATTERNS:
            leaks += sum(
                1
                for match in pattern.finditer(result.snippet)
                if "[REDACTED]" not in match.group(0)
            )
        leaks += sum(
            term.casefold() in result.snippet.casefold() for term in forbidden_terms
        )
    return leaks


def relative_source(source_path: str, workspace: Path) -> str:
    try:
        return Path(source_path).resolve().relative_to(workspace).as_posix()
    except ValueError:
        return source_path


def relative_citation(result: QueryResult, workspace: Path) -> str:
    source = relative_source(result.source_path, workspace)
    heading = f"#{result.heading}" if result.heading else ""
    return f"{source}{heading}:L{result.start_line}-L{result.end_line}"


def database_size(path: Path) -> int:
    return sum(candidate.stat().st_size for candidate in path.parent.glob(f"{path.name}*"))


def directory_hash(path: Path) -> str:
    digest = hashlib.sha256()
    for candidate in sorted(item for item in path.rglob("*") if item.is_file()):
        digest.update(candidate.relative_to(path).as_posix().encode("utf-8"))
        digest.update(b"\0")
        digest.update(candidate.read_bytes())
        digest.update(b"\0")
    return digest.hexdigest()


def file_hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def elapsed_ms(started: float) -> float:
    return round((time.perf_counter() - started) * 1000, 3)


def percentile(values: list[float], percentile_value: float) -> float:
    ordered = sorted(values)
    index = min(len(ordered) - 1, max(0, int(len(ordered) * percentile_value) - 1))
    return ordered[index]


def ratio(numerator: float, denominator: int) -> float:
    return round(numerator / denominator, 4) if denominator else 0.0
