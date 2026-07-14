from __future__ import annotations

import hashlib
import sqlite3
from pathlib import Path

from .schema import connect, init_db


def verify_canonical_source(db_path: Path | str, source_path: Path | str) -> dict[str, object]:
    """Compare an indexed record with the current canonical file on disk."""
    resolved = Path(source_path).expanduser().resolve()
    conn = connect(db_path)
    init_db(conn)
    try:
        row = conn.execute(
            "SELECT * FROM documents WHERE source_path = ?",
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

    current_hash = None
    read_error = None
    if resolved.exists():
        try:
            current_hash = hashlib.sha256(resolved.read_bytes()).hexdigest()
        except OSError as exc:
            read_error = str(exc)
    result: dict[str, object] = {
        "source_path": resolved.as_posix(),
        "indexed": True,
        "exists": resolved.exists(),
        "content_hash_match": current_hash == row["source_hash"],
        "indexed_hash": row["source_hash"],
        "current_hash": current_hash,
        "indexed_at": row["updated_at"],
    }
    if read_error:
        result["read_error"] = read_error
    return result


def list_canonical_sources(db_path: Path | str, limit: int = 50) -> list[dict[str, object]]:
    conn = connect(db_path)
    init_db(conn)
    try:
        rows = conn.execute(
            """
            SELECT source_type, source_path, title, workspace, updated_at
            FROM documents
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
