from __future__ import annotations

import sqlite3
from pathlib import Path


DEFAULT_DB_PATH = Path(".bam/memory.db")


def connect(db_path: Path | str = DEFAULT_DB_PATH) -> sqlite3.Connection:
    path = Path(db_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    conn.execute("PRAGMA secure_delete=ON")
    return conn


def init_db(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS records (
          id TEXT PRIMARY KEY,
          source_type TEXT NOT NULL,
          source_path TEXT NOT NULL,
          workspace TEXT NOT NULL,
          title TEXT NOT NULL,
          content TEXT NOT NULL,
          content_hash TEXT NOT NULL,
          metadata_json TEXT NOT NULL,
          updated_at TEXT NOT NULL
        );

        CREATE INDEX IF NOT EXISTS idx_records_source_type
          ON records(source_type);

        CREATE INDEX IF NOT EXISTS idx_records_workspace
          ON records(workspace);

        CREATE VIRTUAL TABLE IF NOT EXISTS records_fts USING fts5(
          id UNINDEXED,
          title,
          content,
          source_path,
          tokenize = 'unicode61'
        );
        """
    )
    _enable_fts_secure_delete(conn)
    conn.commit()


def fts5_available(conn: sqlite3.Connection) -> bool:
    try:
        conn.execute(
            "CREATE VIRTUAL TABLE IF NOT EXISTS temp._bam_fts5_probe USING fts5(x)"
        )
        conn.execute("DROP TABLE IF EXISTS temp._bam_fts5_probe")
        return True
    except sqlite3.DatabaseError:
        return False


def clear_index(conn: sqlite3.Connection) -> None:
    conn.execute("DELETE FROM records_fts")
    conn.execute("DELETE FROM records")
    conn.commit()
    conn.execute("VACUUM")


def _enable_fts_secure_delete(conn: sqlite3.Connection) -> None:
    try:
        conn.execute("INSERT INTO records_fts(records_fts, rank) VALUES('secure-delete', 1)")
    except sqlite3.DatabaseError:
        pass
