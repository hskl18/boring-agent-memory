from __future__ import annotations

import json
import sqlite3
import tempfile
import unittest
from pathlib import Path

from boring_agent_memory.index import build_index


class IndexBuildTests(unittest.TestCase):
    def test_build_indexes_trusted_text_files(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "docs").mkdir()
            (root / "docs" / "memory.md").write_text(
                "# Canonical memory\n\nBM25 recall should cite source files.\n",
                encoding="utf-8",
            )
            (root / "docs" / "binary.bin").write_bytes(b"\x00\x01\x02")
            db_path = root / ".bam" / "memory.db"

            stats = build_index(db_path, ["docs"], workspace=root)

            self.assertEqual(stats["indexed"], 1)
            conn = sqlite3.connect(db_path)
            conn.row_factory = sqlite3.Row
            row = conn.execute("SELECT * FROM records").fetchone()
            self.assertEqual(row["title"], "memory.md")
            self.assertIn("BM25 recall", row["content"])
            metadata = json.loads(row["metadata_json"])
            self.assertEqual(metadata["extension"], ".md")
            conn.close()

    def test_build_expands_include_globs(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "project-a" / "docs").mkdir(parents=True)
            (root / "project-b" / "docs").mkdir(parents=True)
            (root / "project-a" / "docs" / "memory.md").write_text(
                "Agent memory should support glob includes.\n",
                encoding="utf-8",
            )
            (root / "project-b" / "docs" / "notes.md").write_text(
                "Glob includes make example configs work.\n",
                encoding="utf-8",
            )
            db_path = root / ".bam" / "memory.db"

            stats = build_index(db_path, ["project-*/docs"], workspace=root)

            self.assertEqual(stats["indexed"], 2)

    def test_full_rebuild_removes_a_deleted_source(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            docs = root / "docs"
            docs.mkdir()
            retained = docs / "retained.md"
            deleted = docs / "deleted.md"
            retained.write_text("Retained canonical rule.\n", encoding="utf-8")
            deleted.write_text("Deleted canonical rule.\n", encoding="utf-8")
            db_path = root / ".bam" / "memory.db"

            self.assertEqual(build_index(db_path, ["docs"], workspace=root)["indexed"], 2)
            deleted.unlink()
            self.assertEqual(build_index(db_path, ["docs"], workspace=root)["indexed"], 1)

            conn = sqlite3.connect(db_path)
            paths = [row[0] for row in conn.execute("SELECT source_path FROM records")]
            conn.close()
            self.assertEqual(paths, [retained.resolve().as_posix()])

    def test_corrupt_index_fails_without_modifying_canonical_source(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            docs = root / "docs"
            docs.mkdir()
            source = docs / "policy.md"
            content = "Canonical policy remains the source of truth.\n"
            source.write_text(content, encoding="utf-8")
            db_path = root / ".bam" / "memory.db"
            db_path.parent.mkdir()
            db_path.write_bytes(b"not a sqlite database")

            with self.assertRaises(sqlite3.DatabaseError):
                build_index(db_path, ["docs"], workspace=root)

            self.assertEqual(source.read_text(encoding="utf-8"), content)


if __name__ == "__main__":
    unittest.main()
