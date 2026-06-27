from __future__ import annotations

import json
import os
import subprocess
import sys
import unittest
from pathlib import Path

from boring_agent_memory.eval import run_eval


ROOT = Path(__file__).resolve().parents[1]


class EvalTests(unittest.TestCase):
    def test_fixture_eval_reports_retrieval_and_safety_metrics(self) -> None:
        report = run_eval(ROOT / "evals" / "fixtures", ROOT / "evals" / "golden.jsonl")

        metrics = report["metrics"]
        self.assertEqual(metrics["cases"], 7)
        self.assertEqual(metrics["recall_at_1"], 1.0)
        self.assertEqual(metrics["recall_at_3"], 1.0)
        self.assertEqual(metrics["source_accuracy"], 1.0)
        self.assertEqual(metrics["snippet_term_rate"], 1.0)
        self.assertEqual(metrics["privacy_leak_count"], 0)
        self.assertEqual(metrics["stale_detection_rate"], 1.0)
        stale_case = next(case for case in report["cases"] if case["id"] == "stale_mutated_canonical_policy")
        self.assertTrue(stale_case["stale_detected"])

    def test_cli_eval_json(self) -> None:
        env = {**os.environ, "PYTHONPATH": str(ROOT / "src")}
        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "boring_agent_memory.cli",
                "eval",
                "--fixtures",
                str(ROOT / "evals" / "fixtures"),
                "--golden",
                str(ROOT / "evals" / "golden.jsonl"),
                "--json",
            ],
            cwd=ROOT,
            env=env,
            text=True,
            capture_output=True,
            check=True,
        )

        payload = json.loads(result.stdout)
        self.assertEqual(payload["metrics"]["cases"], 7)
        self.assertTrue(payload["passed"])
        self.assertEqual(payload["metrics"]["privacy_leak_count"], 0)
        self.assertEqual(payload["cases"][0]["top_source"], "canonical_docs/skills/job-scout.md")

    def test_cli_eval_gate_can_fail(self) -> None:
        env = {**os.environ, "PYTHONPATH": str(ROOT / "src")}
        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "boring_agent_memory.cli",
                "eval",
                "--fixtures",
                str(ROOT / "evals" / "fixtures"),
                "--golden",
                str(ROOT / "evals" / "golden.jsonl"),
                "--min-recall-at-1",
                "1.1",
                "--json",
            ],
            cwd=ROOT,
            env=env,
            text=True,
            capture_output=True,
        )

        self.assertEqual(result.returncode, 1)
        payload = json.loads(result.stdout)
        self.assertFalse(payload["passed"])
        self.assertIn("recall_at_1", payload["failures"][0])


if __name__ == "__main__":
    unittest.main()
