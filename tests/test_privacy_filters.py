from __future__ import annotations

import sqlite3
import tempfile
import unittest
from pathlib import Path

from boring_agent_memory.index import build_index


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


if __name__ == "__main__":
    unittest.main()
