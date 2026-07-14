from __future__ import annotations

import argparse
import importlib.metadata
import json
import platform
import sqlite3
import subprocess
from pathlib import Path

from boring_agent_memory import __version__
from boring_agent_memory.benchmark import run_benchmark
from boring_agent_memory.embeddings import FastEmbedAdapter


ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the adversarial benchmark-v2 corpus.")
    parser.add_argument("--output", type=Path, help="Write the full JSON report to this path.")
    parser.add_argument("--check", action="store_true", help="Fail if benchmark invariants regress.")
    parser.add_argument("--embedding-model", help="FastEmbed model identifier.")
    parser.add_argument("--embedding-model-path", type=Path, help="Local model directory.")
    parser.add_argument("--embedding-cache", type=Path, help="Optional FastEmbed cache directory.")
    parser.add_argument("--allow-model-download", action="store_true")
    args = parser.parse_args()

    adapter = None
    if args.embedding_model:
        adapter = FastEmbedAdapter(
            model_name=args.embedding_model,
            model_path=args.embedding_model_path,
            allow_download=args.allow_model_download,
            cache_dir=args.embedding_cache,
        )
    elif args.embedding_model_path or args.allow_model_download:
        parser.error("embedding options require --embedding-model")

    report = run_benchmark(
        ROOT / "benchmarks" / "v2" / "corpus",
        ROOT / "benchmarks" / "v2" / "cases.jsonl",
        benchmark_name="benchmark-v2",
        embedding_adapter=adapter,
    )
    report["environment"] = {
        "bam_version": __version__,
        "git_commit": git_commit(),
        "git_dirty": git_dirty(),
        "python": platform.python_version(),
        "sqlite": sqlite3.sqlite_version,
        "system": platform.system(),
        "machine": platform.machine(),
        "fastembed": package_version("fastembed"),
    }
    rendered = json.dumps(report, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8")
    else:
        print(rendered, end="")

    if not args.check:
        return 0
    chunked = report["strategies"]["chunked_bm25"]
    metrics = chunked["metrics"]
    checks = (
        report["corpus"]["cases"] >= 10,
        len(chunked["cases"]) == report["corpus"]["cases"],
        metrics["recall_at_3"] >= 0.8,
        metrics["evidence_recall_at_3"] >= 0.8,
        metrics["stale_conflict_accuracy"] == 1.0,
        metrics["privacy_leak_count"] == 0,
    )
    return 0 if all(checks) else 1


def package_version(name: str) -> str | None:
    try:
        return importlib.metadata.version(name)
    except importlib.metadata.PackageNotFoundError:
        return None


def git_commit() -> str | None:
    result = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=ROOT,
        text=True,
        capture_output=True,
    )
    return result.stdout.strip() if result.returncode == 0 else None


def git_dirty() -> bool | None:
    result = subprocess.run(
        ["git", "status", "--porcelain"],
        cwd=ROOT,
        text=True,
        capture_output=True,
    )
    return bool(result.stdout.strip()) if result.returncode == 0 else None


if __name__ == "__main__":
    raise SystemExit(main())
