from __future__ import annotations

import sqlite3
import tempfile
import unittest
from pathlib import Path

from boring_agent_memory.index import update_index
from boring_agent_memory.query import query_memory
from boring_agent_memory.schema import SCHEMA_VERSION, connect, init_db, schema_version


class SchemaMigrationTests(unittest.TestCase):
    def test_legacy_schema_migrates_transactionally_and_remains_queryable(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "legacy.db"
            raw = sqlite3.connect(db_path)
            self._create_legacy_schema(raw)
            raw.execute(
                "INSERT INTO records VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    "legacy-id",
                    "file",
                    str(Path(tmp) / "policy.md"),
                    tmp,
                    "policy.md",
                    "Legacy migration marker.",
                    "legacy-hash",
                    "{}",
                    "2026-01-01T00:00:00+00:00",
                ),
            )
            raw.commit()
            raw.close()

            conn = connect(db_path)
            init_db(conn)
            self.assertEqual(schema_version(conn), SCHEMA_VERSION)
            self.assertEqual(conn.execute("SELECT count(*) FROM documents").fetchone()[0], 1)
            self.assertEqual(conn.execute("SELECT count(*) FROM chunks").fetchone()[0], 1)
            conn.close()
            self.assertEqual(query_memory(db_path, "Legacy migration marker", limit=1)[0].title, "policy.md")

    def test_dry_run_does_not_migrate_legacy_schema(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "docs").mkdir()
            db_path = root / "legacy.db"
            raw = sqlite3.connect(db_path)
            self._create_legacy_schema(raw)
            raw.close()

            with self.assertRaisesRegex(ValueError, "current index schema"):
                update_index(db_path, ["docs"], workspace=root, dry_run=True)

            raw = sqlite3.connect(db_path)
            self.assertEqual(raw.execute("PRAGMA user_version").fetchone()[0], 0)
            self.assertIsNotNone(
                raw.execute("SELECT 1 FROM sqlite_master WHERE name = 'records'").fetchone()
            )
            raw.close()

    def test_future_schema_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "future.db"
            raw = sqlite3.connect(db_path)
            raw.execute(f"PRAGMA user_version={SCHEMA_VERSION + 1}")
            raw.close()

            conn = connect(db_path)
            with self.assertRaisesRegex(sqlite3.DatabaseError, "newer than supported"):
                init_db(conn)
            conn.close()

    def test_failed_migration_rolls_back_legacy_schema_and_rows(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "legacy.db"
            raw = sqlite3.connect(db_path)
            self._create_legacy_schema(raw)
            for record_id in ("one", "two"):
                raw.execute(
                    "INSERT INTO records VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (
                        record_id,
                        "file",
                        str(Path(tmp) / "same.md"),
                        tmp,
                        "same.md",
                        record_id,
                        record_id,
                        "{}",
                        "2026-01-01T00:00:00+00:00",
                    ),
                )
            raw.commit()
            raw.close()

            conn = connect(db_path)
            with self.assertRaises(sqlite3.IntegrityError):
                init_db(conn)
            conn.close()

            raw = sqlite3.connect(db_path)
            self.assertEqual(raw.execute("PRAGMA user_version").fetchone()[0], 0)
            self.assertEqual(raw.execute("SELECT count(*) FROM records").fetchone()[0], 2)
            self.assertIsNone(
                raw.execute("SELECT 1 FROM sqlite_master WHERE name = 'documents'").fetchone()
            )
            raw.close()

    @staticmethod
    def _create_legacy_schema(conn: sqlite3.Connection) -> None:
        conn.execute(
            """
            CREATE TABLE records (
              id TEXT PRIMARY KEY,
              source_type TEXT NOT NULL,
              source_path TEXT NOT NULL,
              workspace TEXT NOT NULL,
              title TEXT NOT NULL,
              content TEXT NOT NULL,
              content_hash TEXT NOT NULL,
              metadata_json TEXT NOT NULL,
              updated_at TEXT NOT NULL
            )
            """
        )
        conn.execute(
            """
            CREATE VIRTUAL TABLE records_fts USING fts5(
              id UNINDEXED, title, content, source_path
            )
            """
        )


if __name__ == "__main__":
    unittest.main()
