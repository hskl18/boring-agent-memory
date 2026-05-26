from __future__ import annotations

import sqlite3
from pathlib import Path

from .ingest import IngestedRecord, ingest_file, iter_candidate_files
from .schema import clear_index, connect, init_db


def build_index(
    db_path: Path | str,
    includes: list[str],
    excludes: list[str] | None = None,
    workspace: Path | str | None = None,
    source_type: str = "file",
    max_bytes: int = 512 * 1024,
) -> dict[str, int]:
    excludes = excludes or []
    workspace_path = Path(workspace).expanduser().resolve() if workspace else Path.cwd()
    conn = connect(db_path)
    init_db(conn)
    clear_index(conn)

    indexed = 0
    skipped = 0
    for file_path in iter_candidate_files(includes, excludes, workspace_path):
        record = ingest_file(
            file_path,
            workspace=workspace_path,
            source_type=source_type,
            max_bytes=max_bytes,
        )
        if record is None:
            skipped += 1
            continue
        insert_record(conn, record)
        indexed += 1

    conn.commit()
    conn.close()
    return {"indexed": indexed, "skipped": skipped}


def insert_record(conn: sqlite3.Connection, record: IngestedRecord) -> None:
    conn.execute(
        """
        INSERT INTO records (
          id, source_type, source_path, workspace, title, content,
          content_hash, metadata_json, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            record.id,
            record.source_type,
            record.source_path,
            record.workspace,
            record.title,
            record.content,
            record.content_hash,
            record.metadata_json,
            record.updated_at,
        ),
    )
    conn.execute(
        """
        INSERT INTO records_fts (id, title, content, source_path)
        VALUES (?, ?, ?, ?)
        """,
        (record.id, record.title, record.content, record.source_path),
    )

