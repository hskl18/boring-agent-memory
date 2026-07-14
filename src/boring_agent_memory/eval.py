from __future__ import annotations

import json
import re
import shutil
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .canonical import verify_canonical_source
from .index import build_index
from .privacy import SECRET_PATTERNS
from .query import QueryResult, query_memory


@dataclass(frozen=True)
class EvalCase:
    id: str
    query: str
    expected_source: str
    expected_terms: tuple[str, ...] = ()
    forbidden_sources: tuple[str, ...] = ()
    forbidden_terms: tuple[str, ...] = ()
    expected_rank_at_most: int = 3
    limit: int = 3
    mutate_after_build: dict[str, str] | None = None
    expect_stale: bool = False


def run_eval(
    fixture_dir: Path | str,
    golden_path: Path | str | None = None,
    db_path: Path | str | None = None,
    limit: int = 3,
) -> dict[str, Any]:
    fixture_dir = Path(fixture_dir).expanduser().resolve()
    golden_path = Path(golden_path).expanduser().resolve() if golden_path else fixture_dir.parent / "golden.jsonl"
    cases = load_cases(golden_path)

    with tempfile.TemporaryDirectory() as tmp:
        work_fixture = Path(tmp) / "fixtures"
        shutil.copytree(fixture_dir, work_fixture)
        eval_db_path = Path(db_path).expanduser().resolve() if db_path else Path(tmp) / "memory.db"

        build_stats = build_index(
            db_path=eval_db_path,
            includes=[work_fixture.as_posix()],
            workspace=work_fixture,
            source_type="eval_fixture",
        )
        apply_mutations(work_fixture, cases)

        rows = [
            evaluate_case(
                case=case,
                db_path=eval_db_path,
                workspace=work_fixture,
                limit=max(limit, case.limit, case.expected_rank_at_most),
            )
            for case in cases
        ]

    metrics = summarize(rows)
    return {
        "fixture_dir": fixture_dir.as_posix(),
        "golden_path": golden_path.as_posix(),
        "build": build_stats,
        "metrics": metrics,
        "cases": rows,
    }


def evaluate_gates(
    report: dict[str, Any],
    min_recall_at_1: float | None = None,
    min_recall_at_3: float | None = None,
    min_source_accuracy: float | None = None,
    min_snippet_term_rate: float | None = None,
    min_stale_detection_rate: float | None = None,
    max_privacy_leaks: int | None = None,
) -> list[str]:
    metrics = report["metrics"]
    failures: list[str] = []
    threshold_checks = {
        "recall_at_1": min_recall_at_1,
        "recall_at_3": min_recall_at_3,
        "source_accuracy": min_source_accuracy,
        "snippet_term_rate": min_snippet_term_rate,
        "stale_detection_rate": min_stale_detection_rate,
    }
    for metric, minimum in threshold_checks.items():
        if minimum is not None and float(metrics[metric]) < minimum:
            failures.append(f"{metric}={metrics[metric]} is below required {minimum}")

    if max_privacy_leaks is not None and int(metrics["privacy_leak_count"]) > max_privacy_leaks:
        failures.append(
            f"privacy_leak_count={metrics['privacy_leak_count']} exceeds allowed {max_privacy_leaks}"
        )
    return failures


def load_cases(golden_path: Path) -> list[EvalCase]:
    cases: list[EvalCase] = []
    for line_number, line in enumerate(golden_path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        payload = json.loads(line)
        try:
            cases.append(
                EvalCase(
                    id=payload["id"],
                    query=payload["query"],
                    expected_source=payload["expected_source"],
                    expected_terms=tuple(payload.get("expected_terms", ())),
                    forbidden_sources=tuple(payload.get("forbidden_sources", ())),
                    forbidden_terms=tuple(payload.get("forbidden_terms", ())),
                    expected_rank_at_most=int(payload.get("expected_rank_at_most", payload.get("limit", 3))),
                    limit=int(payload.get("limit", 3)),
                    mutate_after_build=payload.get("mutate_after_build"),
                    expect_stale=bool(payload.get("expect_stale", False)),
                )
            )
        except KeyError as exc:
            raise ValueError(f"{golden_path}:{line_number} missing required field {exc}") from exc
    if not cases:
        raise ValueError(f"{golden_path} does not contain any eval cases")
    return cases


def apply_mutations(work_fixture: Path, cases: list[EvalCase]) -> None:
    work_fixture = work_fixture.resolve()
    for case in cases:
        if not case.mutate_after_build:
            continue
        source_path = case.mutate_after_build["source_path"]
        content = case.mutate_after_build["content"]
        target = (work_fixture / source_path).resolve()
        if not target.is_relative_to(work_fixture):
            raise ValueError(f"mutation target escapes fixture directory: {source_path}")
        target.write_text(content, encoding="utf-8")


def evaluate_case(
    case: EvalCase,
    db_path: Path,
    workspace: Path,
    limit: int,
) -> dict[str, Any]:
    workspace = workspace.resolve()
    results = query_memory(
        db_path=db_path,
        query=case.query,
        limit=limit,
        source_type="eval_fixture",
        workspace=workspace,
    )
    expected_path = (workspace / case.expected_source).resolve().as_posix()
    rank = rank_of_expected(results, expected_path)
    top = results[0] if results else None
    snippet_terms_present = terms_present(top, case.expected_terms) if top else False
    privacy_leaks = count_privacy_leaks(results, case.forbidden_terms)
    forbidden_source_ranks = ranked_forbidden_sources(results, workspace, case.forbidden_sources)
    stale_detected = False
    if case.expect_stale or case.forbidden_sources:
        stale_detected = stale_sources_did_not_outrank_expected(rank, forbidden_source_ranks)
        if case.expect_stale and top:
            verification = verify_canonical_source(db_path, top.source_path)
            stale_detected = stale_detected and verification.get("content_hash_match") is False

    return {
        "id": case.id,
        "query": case.query,
        "expected_source": case.expected_source,
        "top_source": relative_source(top.source_path, workspace) if top else None,
        "rank": rank,
        "recall_at_1": rank == 1,
        "recall_at_k": rank is not None and rank <= case.expected_rank_at_most,
        "source_accuracy": top is not None and top.source_path == expected_path,
        "snippet_terms_present": snippet_terms_present,
        "privacy_leak_count": privacy_leaks,
        "forbidden_source_ranks": forbidden_source_ranks,
        "stale_expected": case.expect_stale or bool(case.forbidden_sources),
        "stale_detected": stale_detected,
    }


def rank_of_expected(results: list[QueryResult], expected_path: str) -> int | None:
    for index, result in enumerate(results, start=1):
        if result.source_path == expected_path:
            return index
    return None


def terms_present(result: QueryResult, terms: tuple[str, ...]) -> bool:
    if not terms:
        return True
    haystack = normalize_text(f"{result.title}\n{result.snippet}")
    return all(normalize_text(term) in haystack for term in terms)


def count_privacy_leaks(results: list[QueryResult], forbidden_terms: tuple[str, ...] = ()) -> int:
    count = 0
    for result in results:
        for pattern in SECRET_PATTERNS:
            for match in pattern.finditer(result.snippet):
                if "[REDACTED]" not in match.group(0):
                    count += 1
        lowered = result.snippet.lower()
        for term in forbidden_terms:
            if term.lower() in lowered:
                count += 1
    return count


def ranked_forbidden_sources(
    results: list[QueryResult],
    workspace: Path,
    sources: tuple[str, ...],
) -> dict[str, int | None]:
    forbidden = set(sources)
    ranks: dict[str, int | None] = {source: None for source in sources}
    for result in results:
        relative = relative_source(result.source_path, workspace)
        if relative in forbidden:
            ranks[relative] = rank_of_expected(results, result.source_path)
    return ranks


def stale_sources_did_not_outrank_expected(
    expected_rank: int | None,
    forbidden_source_ranks: dict[str, int | None],
) -> bool:
    if expected_rank is None:
        return False
    return all(rank is None or rank > expected_rank for rank in forbidden_source_ranks.values())


def relative_source(source_path: str, workspace: Path) -> str:
    try:
        return Path(source_path).resolve().relative_to(workspace).as_posix()
    except ValueError:
        return source_path


def summarize(rows: list[dict[str, Any]]) -> dict[str, Any]:
    total = len(rows)
    stale_cases = [row for row in rows if row["stale_expected"]]
    mrr_total = sum((1 / row["rank"]) for row in rows if row["rank"])
    return {
        "cases": total,
        "recall_at_1": ratio(sum(1 for row in rows if row["recall_at_1"]), total),
        "recall_at_3": ratio(sum(1 for row in rows if row["recall_at_k"]), total),
        "mrr": ratio(mrr_total, total),
        "source_accuracy": ratio(sum(1 for row in rows if row["source_accuracy"]), total),
        "snippet_term_rate": ratio(sum(1 for row in rows if row["snippet_terms_present"]), total),
        "privacy_leak_count": sum(row["privacy_leak_count"] for row in rows),
        "stale_detection_rate": ratio(
            sum(1 for row in stale_cases if row["stale_detected"]),
            len(stale_cases),
        ),
    }


def ratio(numerator: float, denominator: int) -> float:
    if denominator == 0:
        return 0.0
    return round(numerator / denominator, 4)


def normalize_text(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", value.lower()).strip()
