from __future__ import annotations

import sqlite3
from pathlib import Path

from .chunking import chunk_text


DEFAULT_DB_PATH = Path(".bam/memory.db")
SCHEMA_VERSION = 2


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
    """Create or transactionally migrate the index schema."""
    version = schema_version(conn)
    if version > SCHEMA_VERSION:
        raise sqlite3.DatabaseError(
            f"index schema {version} is newer than supported schema {SCHEMA_VERSION}"
        )

    has_legacy_records = _table_exists(conn, "records")
    if version == SCHEMA_VERSION and not has_legacy_records:
        _enable_fts_secure_delete(conn)
        return

    started_transaction = not conn.in_transaction
    if started_transaction:
        conn.execute("BEGIN IMMEDIATE")
    try:
        if has_legacy_records:
            _migrate_v1_to_v2(conn)
        else:
            _create_v2_schema(conn)
        conn.execute(f"PRAGMA user_version={SCHEMA_VERSION}")
        _enable_fts_secure_delete(conn)
        if started_transaction:
            conn.commit()
    except Exception:
        if started_transaction:
            conn.rollback()
        raise


def schema_version(conn: sqlite3.Connection) -> int:
    return int(conn.execute("PRAGMA user_version").fetchone()[0])


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
    """Clear index rows inside the caller's transaction."""
    conn.execute("DELETE FROM chunks_fts")
    conn.execute("DELETE FROM chunks")
    conn.execute("DELETE FROM documents")
    conn.execute("DELETE FROM index_metadata")


def _create_v2_schema(conn: sqlite3.Connection) -> None:
    statements = (
        """CREATE TABLE IF NOT EXISTS documents (
          id TEXT PRIMARY KEY,
          source_type TEXT NOT NULL,
          source_path TEXT NOT NULL,
          workspace TEXT NOT NULL,
          title TEXT NOT NULL,
          content TEXT NOT NULL,
          source_hash TEXT NOT NULL,
          content_hash TEXT NOT NULL,
          metadata_json TEXT NOT NULL,
          updated_at TEXT NOT NULL,
          UNIQUE(workspace, source_type, source_path)
        )""",
        """CREATE INDEX IF NOT EXISTS idx_documents_source_type
          ON documents(source_type)""",
        """CREATE INDEX IF NOT EXISTS idx_documents_workspace
          ON documents(workspace)""",
        """CREATE INDEX IF NOT EXISTS idx_documents_source_hash
          ON documents(source_hash)""",
        """CREATE TABLE IF NOT EXISTS chunks (
          id TEXT PRIMARY KEY,
          document_id TEXT NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
          heading TEXT NOT NULL,
          heading_key TEXT NOT NULL,
          ordinal INTEGER NOT NULL,
          start_line INTEGER NOT NULL,
          end_line INTEGER NOT NULL,
          content TEXT NOT NULL,
          content_hash TEXT NOT NULL,
          UNIQUE(document_id, heading_key, ordinal)
        )""",
        """CREATE INDEX IF NOT EXISTS idx_chunks_document_id
          ON chunks(document_id)""",
        """CREATE VIRTUAL TABLE IF NOT EXISTS chunks_fts USING fts5(
          chunk_id UNINDEXED,
          title,
          heading,
          content,
          source_path,
          tokenize = 'unicode61'
        )""",
        """CREATE TABLE IF NOT EXISTS index_metadata (
          singleton INTEGER PRIMARY KEY CHECK(singleton = 1),
          config_fingerprint TEXT NOT NULL,
          config_json TEXT NOT NULL,
          built_at TEXT NOT NULL,
          chunker_version INTEGER NOT NULL,
          chunk_size INTEGER NOT NULL
        )""",
        """CREATE VIEW IF NOT EXISTS records AS
          SELECT
            id, source_type, source_path, workspace, title, content,
            content_hash, metadata_json, updated_at
          FROM documents""",
    )
    for statement in statements:
        conn.execute(statement)


def _migrate_v1_to_v2(conn: sqlite3.Connection) -> None:
    legacy_rows = conn.execute("SELECT * FROM records ORDER BY source_path").fetchall()
    conn.execute("DROP TABLE IF EXISTS records_fts")
    conn.execute("ALTER TABLE records RENAME TO legacy_records")
    _create_v2_schema(conn)

    for row in legacy_rows:
        chunk = chunk_text(row["id"], row["content"], "", max_chars=0)[0]
        conn.execute(
            """
            INSERT INTO documents (
              id, source_type, source_path, workspace, title, content,
              source_hash, content_hash, metadata_json, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                row["id"],
                row["source_type"],
                row["source_path"],
                row["workspace"],
                row["title"],
                row["content"],
                "",
                chunk.content_hash,
                row["metadata_json"],
                row["updated_at"],
            ),
        )
        conn.execute(
            """
            INSERT INTO chunks (
              id, document_id, heading, heading_key, ordinal,
              start_line, end_line, content, content_hash
            ) VALUES (?, ?, '', 'document', 0, 1, ?, ?, ?)
            """,
            (
                chunk.id,
                row["id"],
                chunk.end_line,
                chunk.content,
                chunk.content_hash,
            ),
        )
        conn.execute(
            """
            INSERT INTO chunks_fts (chunk_id, title, heading, content, source_path)
            VALUES (?, ?, '', ?, ?)
            """,
            (chunk.id, row["title"], chunk.content, row["source_path"]),
        )

    conn.execute("DROP TABLE legacy_records")


def _table_exists(conn: sqlite3.Connection, table: str) -> bool:
    row = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?",
        (table,),
    ).fetchone()
    return row is not None


def _enable_fts_secure_delete(conn: sqlite3.Connection) -> None:
    try:
        conn.execute("INSERT INTO chunks_fts(chunks_fts, rank) VALUES('secure-delete', 1)")
    except sqlite3.DatabaseError:
        pass
