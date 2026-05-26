from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from boring_agent_memory.index import build_index
from boring_agent_memory.query import query_memory


class QueryRankingTests(unittest.TestCase):
    def test_title_match_ranks_above_body_only_match(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "notes").mkdir()
            (root / "notes" / "chrome-cdp.md").write_text(
                "Use the real Chrome profile for debugging authenticated browser flows.\n",
                encoding="utf-8",
            )
            (root / "notes" / "browser.md").write_text(
                "This file mentions chrome cdp once in the body but is mostly unrelated.\n",
                encoding="utf-8",
            )
            db_path = root / ".bam" / "memory.db"
            build_index(db_path, ["notes"], workspace=root)

            results = query_memory(db_path, "chrome cdp", limit=2)

            self.assertGreaterEqual(len(results), 2)
            self.assertEqual(results[0].title, "chrome-cdp.md")
            self.assertIn("source_path", results[0].to_dict())
            self.assertIn("snippet", results[0].to_dict())

    def test_like_fallback_handles_punctuation_query(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "docs").mkdir()
            (root / "docs" / "route.md").write_text(
                "The local route is http://localhost:3000/app/inbox.\n",
                encoding="utf-8",
            )
            db_path = root / ".bam" / "memory.db"
            build_index(db_path, ["docs"], workspace=root)

            results = query_memory(db_path, "localhost:3000/app/inbox", limit=1)

            self.assertEqual(len(results), 1)
            self.assertEqual(results[0].title, "route.md")


if __name__ == "__main__":
    unittest.main()

