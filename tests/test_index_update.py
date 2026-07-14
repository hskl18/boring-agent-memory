from __future__ import annotations

import hashlib
import os
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from boring_agent_memory.index import build_index, update_index
from boring_agent_memory.query import query_memory


class IndexUpdateTests(unittest.TestCase):
    def test_dry_run_and_apply_report_exact_add_modify_move_remove_changes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            docs = root / "docs"
            docs.mkdir()
            modified = docs / "modified.md"
            moved = docs / "moved.md"
            removed = docs / "removed.md"
            modified.write_text("Old policy value.\n", encoding="utf-8")
            moved.write_text("Stable move marker.\n", encoding="utf-8")
            removed.write_text("Remove marker.\n", encoding="utf-8")
            db_path = root / ".bam" / "memory.db"
            build_index(db_path, ["docs"], workspace=root)

            modified.write_text("New policy value.\n", encoding="utf-8")
            moved.rename(docs / "renamed.md")
            removed.unlink()
            (docs / "added.md").write_text("Added marker.\n", encoding="utf-8")
            before_files = self._database_files(db_path)

            dry_run = update_index(db_path, ["docs"], workspace=root, dry_run=True)

            self.assertEqual(
                {key: dry_run[key] for key in ("added", "modified", "moved", "removed")},
                {"added": 1, "modified": 1, "moved": 1, "removed": 1},
            )
            self.assertFalse(dry_run["applied"])
            self.assertEqual(self._database_files(db_path), before_files)

            applied = update_index(db_path, ["docs"], workspace=root)

            self.assertTrue(applied["applied"])
            conn = sqlite3.connect(db_path)
            paths = {Path(row[0]).name for row in conn.execute("SELECT source_path FROM documents")}
            conn.close()
            self.assertEqual(paths, {"added.md", "modified.md", "renamed.md"})
            self.assertEqual(query_memory(db_path, "Remove"), [])
            self.assertEqual(query_memory(db_path, "New policy value", limit=1)[0].title, "modified.md")

            before_noop = self._database_files(db_path)
            noop = update_index(db_path, ["docs"], workspace=root)
            self.assertEqual(noop["unchanged"], 3)
            self.assertEqual(self._database_files(db_path), before_noop)

    def test_failure_before_commit_keeps_previous_index_queryable(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "docs").mkdir()
            source = root / "docs" / "policy.md"
            source.write_text("Previous atomic marker.\n", encoding="utf-8")
            db_path = root / ".bam" / "memory.db"
            build_index(db_path, ["docs"], workspace=root)
            source.write_text("Replacement atomic marker.\n", encoding="utf-8")

            def interrupt(_: sqlite3.Connection) -> None:
                raise RuntimeError("simulated interruption")

            with self.assertRaisesRegex(RuntimeError, "simulated interruption"):
                update_index(
                    db_path,
                    ["docs"],
                    workspace=root,
                    before_commit=interrupt,
                )

            self.assertEqual(
                query_memory(db_path, "Previous atomic marker", limit=1)[0].title,
                "policy.md",
            )
            self.assertEqual(query_memory(db_path, "Replacement"), [])

    def test_ambiguous_duplicate_hashes_are_not_reported_as_moves(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "docs").mkdir()
            for name in ("one.md", "two.md"):
                (root / "docs" / name).write_text("Duplicate content.\n", encoding="utf-8")
            db_path = root / ".bam" / "memory.db"
            build_index(db_path, ["docs"], workspace=root)
            (root / "docs" / "one.md").rename(root / "docs" / "three.md")
            (root / "docs" / "two.md").rename(root / "docs" / "four.md")

            report = update_index(db_path, ["docs"], workspace=root, dry_run=True)

            self.assertEqual(report["moved"], 0)
            self.assertEqual(report["added"], 2)
            self.assertEqual(report["removed"], 2)

    def test_process_interruption_before_commit_preserves_previous_index(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "docs").mkdir()
            source = root / "docs" / "policy.md"
            source.write_text("Durable pre-interrupt value.\n", encoding="utf-8")
            db_path = root / ".bam" / "memory.db"
            build_index(db_path, ["docs"], workspace=root)
            source.write_text("Uncommitted interrupted value.\n", encoding="utf-8")
            script = (
                "import os\n"
                "from boring_agent_memory.index import update_index\n"
                f"update_index({str(db_path)!r}, ['docs'], workspace={str(root)!r}, "
                "before_commit=lambda conn: os._exit(91))\n"
            )

            result = subprocess.run(
                [sys.executable, "-c", script],
                cwd=root,
                env={
                    **os.environ,
                    "PYTHONPATH": str(Path(__file__).resolve().parents[1] / "src"),
                },
            )

            self.assertEqual(result.returncode, 91)
            self.assertEqual(
                query_memory(db_path, "pre-interrupt", limit=1)[0].title,
                "policy.md",
            )
            self.assertEqual(query_memory(db_path, "Uncommitted"), [])

    def test_unreadable_existing_source_aborts_without_removing_indexed_document(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "docs").mkdir()
            source = root / "docs" / "policy.custom"
            source.write_text("Readable canonical fallback.\n", encoding="utf-8")
            db_path = root / ".bam" / "memory.db"
            build_index(db_path, ["docs"], workspace=root)
            source.chmod(0)
            try:
                with self.assertRaisesRegex(OSError, "candidate source"):
                    update_index(db_path, ["docs"], workspace=root)
            finally:
                source.chmod(0o600)

            self.assertEqual(
                query_memory(db_path, "Readable canonical fallback", limit=1)[0].title,
                "policy.custom",
            )

    def test_inaccessible_source_directory_aborts_without_removal(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            private = root / "docs" / "private"
            private.mkdir(parents=True)
            source = private / "policy.md"
            source.write_text("Nested canonical fallback.\n", encoding="utf-8")
            db_path = root / ".bam" / "memory.db"
            build_index(db_path, ["docs"], workspace=root)
            private.chmod(0)
            try:
                with self.assertRaisesRegex(OSError, "indexed source|candidate source"):
                    update_index(db_path, ["docs"], workspace=root)
            finally:
                private.chmod(0o700)

            self.assertEqual(
                query_memory(db_path, "Nested canonical fallback", limit=1)[0].title,
                "policy.md",
            )

    @staticmethod
    def _database_files(db_path: Path) -> dict[str, str]:
        return {
            path.name: hashlib.sha256(path.read_bytes()).hexdigest()
            for path in db_path.parent.glob(f"{db_path.name}*")
        }


if __name__ == "__main__":
    unittest.main()
