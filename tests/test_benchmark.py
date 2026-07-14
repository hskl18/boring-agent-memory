from __future__ import annotations

import json
import unittest
from pathlib import Path

from boring_agent_memory.benchmark import load_benchmark_cases, run_benchmark


ROOT = Path(__file__).resolve().parents[1]
BENCHMARK = ROOT / "benchmarks" / "v1"


class FakeEmbeddingAdapter:
    model_id = "fixture/fake"

    @staticmethod
    def embed_documents(texts: list[str]) -> list[list[float]]:
        return [[float(len(text)), 1.0] for text in texts]

    @staticmethod
    def embed_query(text: str) -> list[float]:
        return [float(len(text)), 1.0]


class BenchmarkTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.report = run_benchmark(BENCHMARK / "corpus", BENCHMARK / "cases.jsonl")

    def test_versioned_corpus_has_six_balanced_categories(self) -> None:
        cases = load_benchmark_cases(BENCHMARK / "cases.jsonl")

        self.assertEqual(len(cases), 120)
        self.assertEqual(self.report["corpus"]["documents"], 80)
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
        bm25 = self.report["strategies"]["whole_document_bm25"]["metrics"]
        grep = self.report["strategies"]["exact_phrase_grep"]["metrics"]

        self.assertGreaterEqual(bm25["recall_at_3"], 0.95)
        self.assertGreater(bm25["recall_at_3"], grep["recall_at_3"])
        self.assertEqual(bm25["no_answer_precision"], 1.0)
        self.assertEqual(bm25["privacy_leak_count"], 0)

    def test_unrun_semantic_strategies_are_explicit(self) -> None:
        self.assertEqual(self.report["strategies"]["dense"]["status"], "not_run")
        self.assertEqual(self.report["strategies"]["hybrid_rrf"]["status"], "not_run")

    def test_raw_rows_can_regenerate_strategy_summary(self) -> None:
        strategy = self.report["strategies"]["chunked_bm25"]
        positive = [row for row in strategy["cases"] if row["expected_source"] is not None]
        recall_at_1 = sum(row["rank"] == 1 for row in positive) / len(positive)

        self.assertEqual(round(recall_at_1, 4), strategy["metrics"]["recall_at_1"])
        self.assertEqual(len(strategy["cases"]), 120)


class AdversarialBenchmarkTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        benchmark = ROOT / "benchmarks" / "v2"
        cls.report = run_benchmark(
            benchmark / "corpus",
            benchmark / "cases.jsonl",
            benchmark_name="benchmark-v2",
        )

    def test_v2_covers_adversarial_categories_and_raw_evidence(self) -> None:
        self.assertEqual(
            set(self.report["corpus"]["category_counts"]),
            {
                "code_symbol",
                "duplicate_heading",
                "embedded_secret",
                "negative_no_answer",
                "stale_conflict",
                "vague_query",
            },
        )
        chunked = self.report["strategies"]["chunked_bm25"]
        self.assertEqual(len(chunked["cases"]), self.report["corpus"]["cases"])
        self.assertEqual(chunked["metrics"]["privacy_leak_count"], 0)
        self.assertEqual(chunked["metrics"]["stale_conflict_accuracy"], 1.0)

    def test_chunking_improves_evidence_level_recall(self) -> None:
        whole = self.report["strategies"]["whole_document_bm25"]["metrics"]
        chunked = self.report["strategies"]["chunked_bm25"]["metrics"]

        self.assertGreater(chunked["evidence_recall_at_3"], whole["evidence_recall_at_3"])

    def test_explicit_fake_adapter_runs_dense_and_hybrid_slots(self) -> None:
        benchmark = ROOT / "benchmarks" / "v2"
        report = run_benchmark(
            benchmark / "corpus",
            benchmark / "cases.jsonl",
            benchmark_name="benchmark-v2",
            embedding_adapter=FakeEmbeddingAdapter(),
        )

        self.assertEqual(report["strategies"]["dense"]["status"], "run")
        self.assertEqual(report["strategies"]["hybrid_rrf"]["status"], "run")
        self.assertEqual(
            report["strategies"]["hybrid_rrf"]["parameters"]["fusion"],
            "weighted_rrf",
        )
        for strategy in ("whole_document_bm25", "chunked_bm25"):
            self.assertEqual(
                report["strategies"][strategy]["index"]["config_fingerprint"],
                self.report["strategies"][strategy]["index"]["config_fingerprint"],
            )

    def test_raw_case_identities_repeat_across_random_workspaces(self) -> None:
        benchmark = ROOT / "benchmarks" / "v2"
        first = run_benchmark(
            benchmark / "corpus",
            benchmark / "cases.jsonl",
            benchmark_name="benchmark-v2",
            embedding_adapter=FakeEmbeddingAdapter(),
        )
        second = run_benchmark(
            benchmark / "corpus",
            benchmark / "cases.jsonl",
            benchmark_name="benchmark-v2",
            embedding_adapter=FakeEmbeddingAdapter(),
        )

        for strategy in (
            "whole_document_bm25",
            "chunked_bm25",
            "exact_phrase_grep",
            "dense",
            "hybrid_rrf",
        ):
            self.assertEqual(
                first["strategies"][strategy]["cases"],
                second["strategies"][strategy]["cases"],
            )

    def test_committed_snapshot_matches_reproducible_raw_evidence(self) -> None:
        snapshot_path = (
            ROOT / "benchmarks" / "v2" / "results" / "python-3.14-macos-arm64.json"
        )
        snapshot = json.loads(snapshot_path.read_text(encoding="utf-8"))

        self.assertEqual(snapshot["corpus"], self.report["corpus"])
        for strategy in (
            "whole_document_bm25",
            "chunked_bm25",
            "exact_phrase_grep",
        ):
            self.assertEqual(
                snapshot["strategies"][strategy]["cases"],
                self.report["strategies"][strategy]["cases"],
            )
            self.assertEqual(
                snapshot["strategies"][strategy]["metrics"],
                self.report["strategies"][strategy]["metrics"],
            )
        for strategy in ("whole_document_bm25", "chunked_bm25"):
            self.assertEqual(
                snapshot["strategies"][strategy]["index"]["config_fingerprint"],
                self.report["strategies"][strategy]["index"]["config_fingerprint"],
            )


if __name__ == "__main__":
    unittest.main()
