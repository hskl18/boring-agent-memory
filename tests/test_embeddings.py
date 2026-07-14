from __future__ import annotations

import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import patch

from boring_agent_memory.embeddings import (
    DenseIndex,
    EmbeddingDocument,
    FastEmbedAdapter,
    load_embedding_documents,
    reciprocal_rank_fusion,
)
from boring_agent_memory.index import build_index
from boring_agent_memory.query import QueryResult


class FakeAdapter:
    model_id = "deterministic-fake"

    def __init__(self) -> None:
        self.document_inputs: list[str] = []
        self.query_inputs: list[str] = []

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        self.document_inputs.extend(texts)
        return [self._embed(text) for text in texts]

    def embed_query(self, text: str) -> list[float]:
        self.query_inputs.append(text)
        return self._embed(text)

    @staticmethod
    def _embed(text: str) -> list[float]:
        lowered = text.lower()
        return [float("alpha" in lowered), float("beta" in lowered), 1.0]


class EmbeddingTests(unittest.TestCase):
    def test_fastembed_requires_explicit_download_permission_or_local_path(self) -> None:
        with self.assertRaisesRegex(ValueError, "local embedding model path"):
            FastEmbedAdapter("fixture/model")

    def test_local_adapter_passes_strict_offline_arguments(self) -> None:
        calls: list[dict[str, object]] = []
        fake_module = types.ModuleType("fastembed")

        class FakeTextEmbedding:
            def __init__(self, **kwargs: object) -> None:
                calls.append(kwargs)

            def embed(self, texts: list[str]):
                return iter([[1.0, 0.0] for _ in texts])

        fake_module.TextEmbedding = FakeTextEmbedding  # type: ignore[attr-defined]
        with tempfile.TemporaryDirectory() as tmp, patch.dict(
            sys.modules, {"fastembed": fake_module}
        ):
            adapter = FastEmbedAdapter("fixture/model", model_path=tmp)
            self.assertEqual(adapter.embed_query("query"), [1.0, 0.0])

        self.assertEqual(calls[0]["specific_model_path"], str(Path(tmp).resolve()))
        self.assertTrue(calls[0]["local_files_only"])

    def test_fastembed_adapter_redacts_direct_document_and_query_calls(self) -> None:
        captured: list[str] = []
        fake_module = types.ModuleType("fastembed")

        class FakeTextEmbedding:
            def __init__(self, **_: object) -> None:
                pass

            def embed(self, texts: list[str]):
                captured.extend(texts)
                return iter([[1.0, 0.0] for _ in texts])

        fake_module.TextEmbedding = FakeTextEmbedding  # type: ignore[attr-defined]
        forbidden = "ghp_adapterfixture12345678901234567890"
        with tempfile.TemporaryDirectory() as tmp, patch.dict(
            sys.modules, {"fastembed": fake_module}
        ):
            adapter = FastEmbedAdapter("fixture/model", model_path=tmp)
            adapter.embed_documents([f"document {forbidden}"])
            adapter.embed_query(f"query {forbidden}")

        self.assertEqual(len(captured), 2)
        self.assertTrue(all("[REDACTED]" in text for text in captured))
        self.assertTrue(all(forbidden not in text for text in captured))

    def test_dense_index_and_hybrid_fusion_are_deterministic(self) -> None:
        alpha = self._result("alpha", "alpha.md")
        beta = self._result("beta", "beta.md")
        adapter = FakeAdapter()
        index = DenseIndex.build(
            adapter,
            [
                EmbeddingDocument(alpha, "alpha rule"),
                EmbeddingDocument(beta, "beta rule"),
            ],
        )

        dense = index.query("beta", limit=2)
        fused = reciprocal_rank_fusion([alpha, beta], dense, limit=2)

        self.assertEqual(dense[0].title, "beta.md")
        self.assertEqual([result.strategy for result in fused], ["hybrid_rrf", "hybrid_rrf"])
        self.assertEqual(len({result.id for result in fused}), 2)

    def test_embedding_input_contains_only_redacted_chunks(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "docs").mkdir()
            forbidden = "ghp_fixturevalue12345678901234567890"
            (root / "docs" / "credentials.md").write_text(
                f"Credential procedure.\n\n{forbidden}\n",
                encoding="utf-8",
            )
            db_path = root / ".bam" / "memory.db"
            build_index(db_path, ["docs"], workspace=root)
            adapter = FakeAdapter()

            DenseIndex.build(adapter, load_embedding_documents(db_path, workspace=root))

            self.assertTrue(any("[REDACTED]" in text for text in adapter.document_inputs))
            self.assertFalse(any(forbidden in text for text in adapter.document_inputs))

    def test_secret_shaped_filename_is_redacted_before_embedding(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "docs").mkdir()
            forbidden = "ghp_titlefixture12345678901234567890"
            (root / "docs" / f"{forbidden}.md").write_text(
                "Credential rotation procedure.\n",
                encoding="utf-8",
            )
            db_path = root / ".bam" / "memory.db"
            build_index(db_path, ["docs"], workspace=root)
            adapter = FakeAdapter()

            DenseIndex.build(adapter, load_embedding_documents(db_path, workspace=root))

            self.assertTrue(any("[REDACTED]" in text for text in adapter.document_inputs))
            self.assertFalse(any(forbidden in text for text in adapter.document_inputs))

    def test_secret_shaped_query_is_redacted_before_embedding(self) -> None:
        forbidden = "ghp_queryfixture12345678901234567890"
        adapter = FakeAdapter()
        index = DenseIndex.build(
            adapter,
            [EmbeddingDocument(self._result("alpha", "alpha.md"), "alpha rule")],
        )

        index.query(f"rotate {forbidden}")

        self.assertEqual(len(adapter.query_inputs), 1)
        self.assertIn("[REDACTED]", adapter.query_inputs[0])
        self.assertNotIn(forbidden, adapter.query_inputs[0])

    @staticmethod
    def _result(chunk_id: str, title: str) -> QueryResult:
        return QueryResult(
            id=chunk_id,
            chunk_id=chunk_id,
            source_type="fixture",
            source_path=f"/tmp/{title}",
            workspace="/tmp",
            title=title,
            heading="",
            start_line=1,
            end_line=1,
            citation=f"/tmp/{title}:L1-L1",
            score=0.0,
            snippet=title,
            strategy="fixture",
        )


if __name__ == "__main__":
    unittest.main()
