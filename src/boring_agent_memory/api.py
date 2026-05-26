from __future__ import annotations

from pathlib import Path

from .query import QueryResult, query_memory
from .schema import DEFAULT_DB_PATH


def memory_query(
    query: str,
    limit: int = 5,
    source_type: str | None = None,
    db_path: Path | str = DEFAULT_DB_PATH,
) -> list[QueryResult]:
    """Small agent-facing query API."""
    return query_memory(
        db_path=db_path,
        query=query,
        limit=limit,
        source_type=source_type,
    )
