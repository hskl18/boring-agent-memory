from __future__ import annotations

import unittest
from pathlib import Path

from boring_agent_memory.benchmark import load_benchmark_cases, run_benchmark


ROOT = Path(__file__).resolve().parents[1]
BENCHMARK = ROOT / "benchmarks" / "v1"


class BenchmarkTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.report = run_benchmark(BENCHMARK / "corpus", BENCHMARK / "cases.jsonl")

    def test_versioned_corpus_has_six_balanced_categories(self) -> None:
        cases = load_benchmark_cases(BENCHMARK / "cases.jsonl")

        self.assertEqual(len(cases), 120)
        self.assertEqual(
            self.report["corpus"]["category_counts"],
            {
                "exact_operational": 20,
                "negative_no_answer": 20,
                "path_scoping": 20,
                "secret_bearing": 20,
                "stale_conflict": 20,
                "vague_semantic": 20,
            },
        )

    def test_bm25_beats_exact_phrase_grep_without_leaking_secrets(self) -> None:
        bm25 = self.report["strategies"]["bm25"]["metrics"]
        grep = self.report["strategies"]["exact_phrase_grep"]["metrics"]

        self.assertGreaterEqual(bm25["recall_at_3"], 0.95)
        self.assertGreater(bm25["recall_at_3"], grep["recall_at_3"])
        self.assertEqual(bm25["no_answer_precision"], 1.0)
        self.assertEqual(bm25["privacy_leak_count"], 0)

    def test_unrun_semantic_strategies_are_explicit(self) -> None:
        self.assertEqual(self.report["strategies"]["embeddings"]["status"], "not_run")
        self.assertEqual(self.report["strategies"]["hybrid"]["status"], "not_run")


if __name__ == "__main__":
    unittest.main()
