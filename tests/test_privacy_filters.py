from __future__ import annotations

import sqlite3
import tempfile
import unittest
from pathlib import Path

from boring_agent_memory.embeddings import load_embedding_documents
from boring_agent_memory.index import build_index
from boring_agent_memory.query import query_memory


class PrivacyFilterTests(unittest.TestCase):
    def test_secret_paths_are_excluded_and_content_is_redacted(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            password_name = "PASS" + "WORD"
            token_name = "SERVICE" + "_TOKEN"
            synthetic_value = "synthetic-token-for-redaction-test"
            (root / ".env").write_text(f"{password_name}=should-not-index\n", encoding="utf-8")
            (root / "docs").mkdir()
            (root / "docs" / "api.md").write_text(
                f"{token_name}={synthetic_value}\n"
                "Use canonical docs for truth.\n",
                encoding="utf-8",
            )
            db_path = root / ".bam" / "memory.db"

            stats = build_index(db_path, ["."], workspace=root)

            self.assertEqual(stats["indexed"], 1)
            conn = sqlite3.connect(db_path)
            row = conn.execute("SELECT source_path, content FROM records").fetchone()
            conn.close()
            self.assertTrue(row[0].endswith("api.md"))
            self.assertIn("[REDACTED]", row[1])
            self.assertNotIn(synthetic_value, row[1])

    def test_multiline_redaction_preserves_canonical_line_citations(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "docs").mkdir()
            private_lines = "synthetic-private-line-one\nsynthetic-private-line-two"
            source = root / "docs" / "policy.md"
            source.write_text(
                "# Policy\n\n"
                "-----BEGIN PRIVATE KEY-----\n"
                f"{private_lines}\n"
                "-----END PRIVATE KEY-----\n\n"
                "## After\n\n"
                "AFTER_MARKER remains on its canonical line.\n",
                encoding="utf-8",
            )
            db_path = root / ".bam" / "memory.db"
            build_index(db_path, ["docs"], workspace=root)

            result = query_memory(db_path, "AFTER_MARKER", limit=1)[0]
            embedding_inputs = [
                document.text for document in load_embedding_documents(db_path, workspace=root)
            ]

            self.assertEqual(result.heading, "Policy > After")
            self.assertEqual((result.start_line, result.end_line), (8, 10))
            self.assertTrue(result.citation.endswith("#Policy > After:L8-L10"))
            self.assertNotIn(private_lines, result.snippet)
            self.assertFalse(any(private_lines in text for text in embedding_inputs))
            conn = sqlite3.connect(db_path)
            indexed_content = conn.execute("SELECT content FROM documents").fetchone()[0]
            conn.close()
            self.assertNotIn(private_lines, indexed_content)
            self.assertEqual(indexed_content.count("\n"), source.read_text(encoding="utf-8").count("\n"))


if __name__ == "__main__":
    unittest.main()
