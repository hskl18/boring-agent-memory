from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from boring_agent_memory.canonical import verify_canonical_source
from boring_agent_memory.index import build_index


class CanonicalVerificationTests(unittest.TestCase):
    def test_verify_canonical_source_detects_changed_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "docs").mkdir()
            source = root / "docs" / "memory.md"
            source.write_text("BM25 recall must cite canonical files.\n", encoding="utf-8")
            db_path = root / ".bam" / "memory.db"

            build_index(db_path, ["docs"], workspace=root)
            before = verify_canonical_source(db_path, source)
            self.assertTrue(before["content_hash_match"])

            source.write_text("Changed canonical file.\n", encoding="utf-8")
            after = verify_canonical_source(db_path, source)
            self.assertFalse(after["content_hash_match"])

    def test_verify_large_source_uses_indexed_raw_hash_without_default_size_limit(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "docs").mkdir()
            source = root / "docs" / "large.md"
            source.write_bytes(b"# Large\n\n" + (b"x" * 600_000))
            db_path = root / ".bam" / "memory.db"

            build_index(db_path, ["docs"], workspace=root, max_bytes=700_000)
            verification = verify_canonical_source(db_path, source)

            self.assertTrue(verification["content_hash_match"])
            self.assertEqual(verification["indexed_hash"], verification["current_hash"])


if __name__ == "__main__":
    unittest.main()
