from __future__ import annotations

import hashlib
import json
import sqlite3
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

from .chunking import CHUNKER_VERSION, DEFAULT_CHUNK_SIZE
from .ingest import IngestedRecord, ingest_file, iter_candidate_files
from .privacy import DEFAULT_EXCLUDE_GLOBS, REDACTION_VERSION, SECRET_PATTERNS
from .schema import SCHEMA_VERSION, clear_index, connect, init_db, schema_version


@dataclass(frozen=True)
class _UpdateOperations:
    delete_ids: tuple[str, ...]
    insert_records: tuple[IngestedRecord, ...]
    removal_paths: tuple[str, ...]


def build_index(
    db_path: Path | str,
    includes: list[str],
    excludes: list[str] | None = None,
    workspace: Path | str | None = None,
    source_type: str = "file",
    max_bytes: int = 512 * 1024,
    chunk_size: int = DEFAULT_CHUNK_SIZE,
) -> dict[str, int]:
    excludes = excludes or []
    workspace_path = _workspace_path(workspace)
    records, skipped = _ingest_candidates(
        includes, excludes, workspace_path, source_type, max_bytes, chunk_size
    )
    config_json, fingerprint = index_configuration(
        includes, excludes, workspace_path, source_type, max_bytes, chunk_size
    )

    conn = connect(db_path)
    try:
        init_db(conn)
        with conn:
            clear_index(conn)
            for record in records:
                insert_record(conn, record)
            _write_index_metadata(conn, config_json, fingerprint, chunk_size)
            _validate_index(conn)
    finally:
        conn.close()
    return {
        "indexed": len(records),
        "chunks": sum(len(record.chunks) for record in records),
        "skipped": skipped,
    }


def update_index(
    db_path: Path | str,
    includes: list[str],
    excludes: list[str] | None = None,
    workspace: Path | str | None = None,
    source_type: str = "file",
    max_bytes: int = 512 * 1024,
    chunk_size: int = DEFAULT_CHUNK_SIZE,
    dry_run: bool = False,
    before_commit: Callable[[sqlite3.Connection], None] | None = None,
) -> dict[str, object]:
    """Apply a hash-based index update in one transaction."""
    path = Path(db_path)
    if not path.exists():
        raise FileNotFoundError(f"index does not exist: {path}; run bam build first")

    excludes = excludes or []
    workspace_path = _workspace_path(workspace)
    records, skipped = _ingest_candidates(
        includes, excludes, workspace_path, source_type, max_bytes, chunk_size
    )
    config_json, fingerprint = index_configuration(
        includes, excludes, workspace_path, source_type, max_bytes, chunk_size
    )

    if dry_run:
        wal_path = Path(f"{path}-wal")
        if wal_path.exists() and wal_path.stat().st_size:
            raise ValueError(
                "dry-run requires a checkpointed index with no pending WAL content"
            )
        conn = sqlite3.connect(
            path.resolve().as_uri() + "?mode=ro&immutable=1",
            uri=True,
        )
        conn.row_factory = sqlite3.Row
        if schema_version(conn) != SCHEMA_VERSION:
            conn.close()
            raise ValueError("dry-run requires a current index schema; run bam build first")
    else:
        conn = connect(path)
    try:
        if not dry_run:
            init_db(conn)
        metadata = conn.execute("SELECT * FROM index_metadata WHERE singleton = 1").fetchone()
        if metadata is None:
            raise ValueError("index has no configuration fingerprint; run bam build once")
        if metadata["config_fingerprint"] != fingerprint:
            raise ValueError(
                "index configuration changed; run bam build before using incremental update"
            )

        existing_rows = conn.execute(
            """
            SELECT
              d.id,
              d.source_path,
              d.source_hash,
              (SELECT count(*) FROM chunks c WHERE c.document_id = d.id) AS chunk_count
            FROM documents d
            WHERE d.workspace = ? AND d.source_type = ?
            ORDER BY source_path
            """,
            (workspace_path.as_posix(), source_type),
        ).fetchall()
        report, operations = _plan_update(existing_rows, records, skipped)
        _validate_removal_access(operations.removal_paths)
        report["applied"] = not dry_run
        report["dry_run"] = dry_run
        if dry_run:
            return report
        if not operations.delete_ids and not operations.insert_records:
            return report

        with conn:
            for document_id in operations.delete_ids:
                delete_document(conn, document_id)
            for record in operations.insert_records:
                insert_record(conn, record)
            _write_index_metadata(conn, config_json, fingerprint, chunk_size)
            _validate_index(conn)
            if before_commit:
                before_commit(conn)
        return report
    finally:
        conn.close()


def insert_record(conn: sqlite3.Connection, record: IngestedRecord) -> None:
    conn.execute(
        """
        INSERT INTO documents (
          id, source_type, source_path, workspace, title, content,
          source_hash, content_hash, metadata_json, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            record.id,
            record.source_type,
            record.source_path,
            record.workspace,
            record.title,
            record.content,
            record.source_hash,
            record.content_hash,
            record.metadata_json,
            record.updated_at,
        ),
    )
    for chunk in record.chunks:
        conn.execute(
            """
            INSERT INTO chunks (
              id, document_id, heading, heading_key, ordinal,
              start_line, end_line, content, content_hash
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                chunk.id,
                record.id,
                chunk.heading,
                chunk.heading_key,
                chunk.ordinal,
                chunk.start_line,
                chunk.end_line,
                chunk.content,
                chunk.content_hash,
            ),
        )
        conn.execute(
            """
            INSERT INTO chunks_fts (chunk_id, title, heading, content, source_path)
            VALUES (?, ?, ?, ?, ?)
            """,
            (chunk.id, record.title, chunk.heading, chunk.content, record.source_path),
        )


def delete_document(conn: sqlite3.Connection, document_id: str) -> None:
    conn.execute(
        "DELETE FROM chunks_fts WHERE chunk_id IN "
        "(SELECT id FROM chunks WHERE document_id = ?)",
        (document_id,),
    )
    conn.execute("DELETE FROM documents WHERE id = ?", (document_id,))


def index_configuration(
    includes: list[str],
    excludes: list[str],
    workspace: Path,
    source_type: str,
    max_bytes: int,
    chunk_size: int,
) -> tuple[str, str]:
    payload = {
        "schema_version": SCHEMA_VERSION,
        "chunker_version": CHUNKER_VERSION,
        "chunk_size": chunk_size,
        "includes": sorted(_normalize_include(value, workspace) for value in includes),
        "excludes": sorted(excludes),
        "workspace": workspace.as_posix(),
        "source_type": source_type,
        "max_bytes": max_bytes,
        "document_id_version": 1,
        "redaction_version": REDACTION_VERSION,
        "tokenizer": "unicode61",
        "privacy_policy": hashlib.sha256(
            json.dumps(
                {
                    "default_excludes": DEFAULT_EXCLUDE_GLOBS,
                    "secret_patterns": [
                        {"pattern": pattern.pattern, "flags": pattern.flags}
                        for pattern in SECRET_PATTERNS
                    ],
                },
                sort_keys=True,
            ).encode("utf-8")
        ).hexdigest(),
    }
    rendered = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return rendered, hashlib.sha256(rendered.encode("utf-8")).hexdigest()


def _ingest_candidates(
    includes: list[str],
    excludes: list[str],
    workspace: Path,
    source_type: str,
    max_bytes: int,
    chunk_size: int,
) -> tuple[list[IngestedRecord], int]:
    records: list[IngestedRecord] = []
    skipped = 0
    try:
        candidates = iter_candidate_files(includes, excludes, workspace)
    except OSError as exc:
        raise OSError(f"failed to scan candidate sources in {workspace}: {exc}") from exc
    for file_path in candidates:
        try:
            record = ingest_file(
                file_path,
                workspace=workspace,
                source_type=source_type,
                max_bytes=max_bytes,
                chunk_size=chunk_size,
            )
        except OSError as exc:
            raise OSError(f"failed to read candidate source {file_path}: {exc}") from exc
        if record is None:
            skipped += 1
            continue
        records.append(record)
    return records, skipped


def _plan_update(
    existing_rows: list[sqlite3.Row],
    records: list[IngestedRecord],
    skipped: int,
) -> tuple[dict[str, object], _UpdateOperations]:
    existing_by_path = {row["source_path"]: row for row in existing_rows}
    current_by_path = {record.source_path: record for record in records}

    unchanged = sorted(
        path
        for path in existing_by_path.keys() & current_by_path.keys()
        if existing_by_path[path]["source_hash"] == current_by_path[path].source_hash
    )
    modified = sorted(
        path
        for path in existing_by_path.keys() & current_by_path.keys()
        if existing_by_path[path]["source_hash"] != current_by_path[path].source_hash
    )
    added = set(current_by_path.keys() - existing_by_path.keys())
    removed = set(existing_by_path.keys() - current_by_path.keys())

    removed_by_hash: dict[str, list[str]] = defaultdict(list)
    added_by_hash: dict[str, list[str]] = defaultdict(list)
    for path in removed:
        removed_by_hash[existing_by_path[path]["source_hash"]].append(path)
    for path in added:
        added_by_hash[current_by_path[path].source_hash].append(path)

    moves: list[dict[str, str]] = []
    for content_hash in sorted(removed_by_hash.keys() & added_by_hash.keys()):
        old_paths = sorted(removed_by_hash[content_hash])
        new_paths = sorted(added_by_hash[content_hash])
        if len(old_paths) == 1 and len(new_paths) == 1:
            old_path = old_paths[0]
            new_path = new_paths[0]
            moves.append({"from": old_path, "to": new_path})
            removed.remove(old_path)
            added.remove(new_path)

    delete_paths = sorted([*removed, *modified, *(move["from"] for move in moves)])
    insert_paths = sorted([*added, *modified, *(move["to"] for move in moves)])
    report: dict[str, object] = {
        "added": len(added),
        "modified": len(modified),
        "moved": len(moves),
        "removed": len(removed),
        "unchanged": len(unchanged),
        "skipped": skipped,
        "chunks_added": sum(len(current_by_path[path].chunks) for path in insert_paths),
        "chunks_removed": sum(
            int(existing_by_path[path]["chunk_count"]) for path in delete_paths
        ),
        "changes": {
            "added": sorted(added),
            "modified": modified,
            "moved": moves,
            "removed": sorted(removed),
        },
    }
    operations = _UpdateOperations(
        delete_ids=tuple(existing_by_path[path]["id"] for path in delete_paths),
        insert_records=tuple(current_by_path[path] for path in insert_paths),
        removal_paths=tuple(sorted(removed)),
    )
    return report, operations


def _write_index_metadata(
    conn: sqlite3.Connection,
    config_json: str,
    fingerprint: str,
    chunk_size: int,
) -> None:
    conn.execute(
        """
        INSERT INTO index_metadata (
          singleton, config_fingerprint, config_json, built_at,
          chunker_version, chunk_size
        ) VALUES (1, ?, ?, ?, ?, ?)
        ON CONFLICT(singleton) DO UPDATE SET
          config_fingerprint = excluded.config_fingerprint,
          config_json = excluded.config_json,
          built_at = excluded.built_at,
          chunker_version = excluded.chunker_version,
          chunk_size = excluded.chunk_size
        """,
        (
            fingerprint,
            config_json,
            datetime.now(timezone.utc).isoformat(),
            CHUNKER_VERSION,
            chunk_size,
        ),
    )


def _workspace_path(workspace: Path | str | None) -> Path:
    return Path(workspace).expanduser().resolve() if workspace else Path.cwd().resolve()


def _normalize_include(value: str, workspace: Path) -> str:
    path = Path(value).expanduser()
    if not path.is_absolute():
        path = workspace / path
    return path.resolve().as_posix()


def _validate_index(conn: sqlite3.Connection) -> None:
    foreign_key_error = conn.execute("PRAGMA foreign_key_check").fetchone()
    if foreign_key_error is not None:
        raise sqlite3.IntegrityError(f"index foreign-key violation: {tuple(foreign_key_error)}")
    chunk_count = conn.execute("SELECT count(*) FROM chunks").fetchone()[0]
    fts_count = conn.execute("SELECT count(*) FROM chunks_fts").fetchone()[0]
    if chunk_count != fts_count:
        raise sqlite3.IntegrityError(
            f"chunk/FTS row mismatch: chunks={chunk_count} fts={fts_count}"
        )


def _validate_removal_access(paths: tuple[str, ...]) -> None:
    """Distinguish real deletion from a source hidden by an access failure."""
    for value in paths:
        path = Path(value)
        try:
            with path.open("rb") as source:
                source.read(1)
        except FileNotFoundError:
            continue
        except OSError as exc:
            raise OSError(
                f"cannot confirm removal of indexed source {path}: {exc}"
            ) from exc
