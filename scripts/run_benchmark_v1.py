from __future__ import annotations

import argparse
import json
import platform
import sqlite3
from pathlib import Path

from boring_agent_memory.benchmark import run_benchmark


ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the versioned benchmark-v1 corpus.")
    parser.add_argument("--output", type=Path, help="Write the full JSON report to this path.")
    parser.add_argument("--check", action="store_true", help="Fail if benchmark invariants regress.")
    args = parser.parse_args()

    report = run_benchmark(
        ROOT / "benchmarks" / "v1" / "corpus",
        ROOT / "benchmarks" / "v1" / "cases.jsonl",
    )
    report["environment"] = {
        "python": platform.python_version(),
        "sqlite": sqlite3.sqlite_version,
        "system": platform.system(),
        "machine": platform.machine(),
    }
    rendered = json.dumps(report, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8")
    else:
        print(rendered, end="")

    if not args.check:
        return 0
    bm25 = report["strategies"]["bm25"]["metrics"]
    checks = (
        report["corpus"]["cases"] >= 100,
        bm25["recall_at_3"] >= 0.95,
        bm25["no_answer_precision"] >= 0.95,
        bm25["privacy_leak_count"] == 0,
    )
    return 0 if all(checks) else 1


if __name__ == "__main__":
    raise SystemExit(main())
