from __future__ import annotations

import sqlite3
from pathlib import Path

from .ingest import ingest_file
from .schema import connect, init_db


def verify_canonical_source(db_path: Path | str, source_path: Path | str) -> dict[str, object]:
    """Compare an indexed record with the current canonical file on disk."""
    resolved = Path(source_path).expanduser().resolve()
    conn = connect(db_path)
    init_db(conn)
    try:
        row = conn.execute(
            "SELECT * FROM records WHERE source_path = ?",
            (resolved.as_posix(),),
        ).fetchone()
    finally:
        conn.close()

    if row is None:
        return {
            "source_path": resolved.as_posix(),
            "indexed": False,
            "exists": resolved.exists(),
            "content_hash_match": False,
        }

    current = ingest_file(
        resolved,
        workspace=Path(row["workspace"]),
        source_type=row["source_type"],
    )
    return {
        "source_path": resolved.as_posix(),
        "indexed": True,
        "exists": resolved.exists(),
        "content_hash_match": current is not None
        and current.content_hash == row["content_hash"],
        "indexed_hash": row["content_hash"],
        "current_hash": current.content_hash if current else None,
        "indexed_at": row["updated_at"],
    }


def list_canonical_sources(db_path: Path | str, limit: int = 50) -> list[dict[str, object]]:
    conn = connect(db_path)
    init_db(conn)
    try:
        rows = conn.execute(
            """
            SELECT source_type, source_path, title, workspace, updated_at
            FROM records
            ORDER BY source_path ASC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
    except sqlite3.DatabaseError:
        return []
    finally:
        conn.close()
    return [dict(row) for row in rows]
