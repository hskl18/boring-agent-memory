"""Measure abstention on benchmark-v1: easy and adversarial no-answer queries, default and strict.

Adversarial no-answer queries pair one fictional system's codename with another system's setting,
such as "current cobalt idle timeout": every term exists in the corpus, but no file answers it.
The default query path falls back to an any-term match and returns something; strict mode does not.
"""

from __future__ import annotations

import argparse
import json
import platform
import re
import shutil
import sqlite3
import tempfile
from collections import defaultdict
from pathlib import Path

from boring_agent_memory import __version__
from boring_agent_memory.benchmark import (
    build_benchmark_index,
    load_benchmark_cases,
    relative_source,
)
from boring_agent_memory.query import query_memory, tokenize_query

ROOT = Path(__file__).resolve().parents[1]
CORPUS = ROOT / "benchmarks" / "v1" / "corpus"
CASE_FILES = (
    ROOT / "benchmarks" / "v1" / "cases.jsonl",
    ROOT / "benchmarks" / "v1" / "adversarial_no_answer.jsonl",
)


def evaluate(db: Path, workspace: Path, strict: bool) -> dict[str, object]:
    by_category: dict[str, list[bool]] = defaultdict(list)
    for path in CASE_FILES:
        for case in load_benchmark_cases(path):
            results = query_memory(
                db, case.query, limit=3, source_type="benchmark_fixture", workspace=workspace, strict=strict
            )
            if case.expected_source is None:
                by_category[case.category].append(not results)
            else:
                sources = [relative_source(result.source_path, workspace) for result in results]
                by_category[case.category].append(case.expected_source in sources)
    positives = [hit for category, hits in by_category.items() if not category.endswith("no_answer") for hit in hits]
    return {
        "positive_recall_at_3": sum(positives) / len(positives),
        "positive_queries": len(positives),
        "recall_at_3_by_category": {
            category: sum(hits) / len(hits) for category, hits in sorted(by_category.items())
            if not category.endswith("no_answer")
        },
        "easy_no_answer_precision": _rate(by_category["negative_no_answer"]),
        "adversarial_no_answer_precision": _rate(by_category["adversarial_no_answer"]),
        "no_answer_queries": {
            "easy": len(by_category["negative_no_answer"]),
            "adversarial": len(by_category["adversarial_no_answer"]),
        },
    }


def coverage_counts(db: Path, workspace: Path) -> dict[str, dict[str, int]]:
    """Share of a query's in-corpus terms found in its default top result, for vague and adversarial queries.

    Kept in the report because a threshold at 0.8 looks like it separates the two, but mostly from query
    length: vague queries have five in-corpus terms, 18 of the 20 adversarial ones have four.
    """

    words = re.compile(r"[a-z0-9_]+")
    vocabulary = {word for path in workspace.rglob("*.md") for word in words.findall(path.read_text().lower())}
    counts: dict[str, dict[str, int]] = {}
    for path in CASE_FILES:
        for case in load_benchmark_cases(path):
            if case.category not in ("vague_semantic", "adversarial_no_answer"):
                continue
            top = query_memory(db, case.query, limit=1, source_type="benchmark_fixture", workspace=workspace)[0]
            text = set(words.findall(Path(top.source_path).read_text().lower()))
            terms = [term.lower() for term in tokenize_query(case.query) if term.lower() in vocabulary]
            share = f"{sum(term in text for term in terms) / len(terms):.2f}"
            bucket = counts.setdefault(case.category, {})
            bucket[share] = bucket.get(share, 0) + 1
    return counts


def _rate(values: list[bool]) -> float:
    return sum(values) / len(values)


def main() -> int:
    parser = argparse.ArgumentParser(description="Measure default and strict abstention on benchmark-v1.")
    parser.add_argument("--output", type=Path, help="Write the JSON report to this path.")
    parser.add_argument("--check", action="store_true", help="Fail if the measured trade-off regresses.")
    args = parser.parse_args()

    with tempfile.TemporaryDirectory() as tmp:
        workspace = (Path(tmp) / "corpus").resolve()
        shutil.copytree(CORPUS, workspace)
        db = Path(tmp) / "chunked.db"
        build_benchmark_index(db, workspace, chunk_size=1600, identity_namespace="benchmark:benchmark-v1")
        report = {
            "benchmark": "benchmark-v1-abstention",
            "package_version": __version__,
            "python": platform.python_version(),
            "sqlite": sqlite3.sqlite_version,
            "platform": f"{platform.system().lower()}-{platform.machine().lower()}",
            "default": evaluate(db, workspace, strict=False),
            "strict": evaluate(db, workspace, strict=True),
            "top_result_in_corpus_term_coverage": coverage_counts(db, workspace),
        }
    text = json.dumps(report, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text, encoding="utf-8")
    print(text, end="")
    if not args.check:
        return 0
    default, strict = report["default"], report["strict"]
    checks = (
        default["positive_recall_at_3"] == 1.0,
        default["easy_no_answer_precision"] == 1.0,
        strict["easy_no_answer_precision"] == 1.0,
        strict["adversarial_no_answer_precision"] == 1.0,
        all(rate == 1.0 for category, rate in strict["recall_at_3_by_category"].items() if category != "vague_semantic"),
    )
    return 0 if all(checks) else 1


if __name__ == "__main__":
    raise SystemExit(main())
