from __future__ import annotations

import re
import sqlite3
from dataclasses import asdict, dataclass
from pathlib import Path

from .schema import connect, init_db
from .snippets import plain_snippet


@dataclass(frozen=True)
class QueryResult:
    id: str
    source_type: str
    source_path: str
    workspace: str
    title: str
    score: float
    snippet: str
    strategy: str

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


def query_memory(
    db_path: Path | str,
    query: str,
    limit: int = 5,
    source_type: str | None = None,
) -> list[QueryResult]:
    conn = connect(db_path)
    init_db(conn)
    try:
        results = _query_memory(conn, query, limit, source_type)
    finally:
        conn.close()
    return results


def _query_memory(
    conn: sqlite3.Connection,
    query: str,
    limit: int,
    source_type: str | None,
) -> list[QueryResult]:
    seen: set[str] = set()
    results: list[QueryResult] = []

    for strategy, fts_query in build_fts_queries(query):
        try:
            rows = run_fts_query(conn, fts_query, limit, source_type)
        except sqlite3.DatabaseError:
            continue
        for row in rows:
            if row["id"] in seen:
                continue
            seen.add(row["id"])
            results.append(row_to_result(row, strategy, query))
            if len(results) >= limit:
                return results

    if len(results) < limit:
        for row in run_like_query(conn, query, limit - len(results), source_type):
            if row["id"] in seen:
                continue
            seen.add(row["id"])
            results.append(row_to_result(row, "like", query))

    return results[:limit]


def build_fts_queries(query: str) -> list[tuple[str, str]]:
    cleaned = query.strip()
    tokens = tokenize_query(cleaned)
    queries: list[tuple[str, str]] = []

    if cleaned:
        queries.append(("phrase", quote_fts(cleaned)))
    if tokens:
        queries.append(("and", " AND ".join(quote_fts(token) for token in tokens)))
        queries.append(("or", " OR ".join(quote_fts(token) for token in tokens)))
    return queries


def tokenize_query(query: str) -> list[str]:
    tokens = re.findall(r"[A-Za-z0-9_./:-]+|[\u4e00-\u9fff]+", query)
    return [token.strip("./:-") for token in tokens if token.strip("./:-")]


def quote_fts(value: str) -> str:
    return '"' + value.replace('"', '""') + '"'


def run_fts_query(
    conn: sqlite3.Connection,
    fts_query: str,
    limit: int,
    source_type: str | None,
) -> list[sqlite3.Row]:
    params: list[object] = [fts_query]
    source_filter = ""
    if source_type:
        source_filter = "AND r.source_type = ?"
        params.append(source_type)
    params.append(limit)

    return conn.execute(
        f"""
        SELECT
          r.id,
          r.source_type,
          r.source_path,
          r.workspace,
          r.title,
          bm25(records_fts, 2.5, 1.0, 0.25) AS score,
          snippet(records_fts, 2, '[', ']', '...', 28) AS snippet
        FROM records_fts
        JOIN records r ON r.id = records_fts.id
        WHERE records_fts MATCH ?
        {source_filter}
        ORDER BY score ASC
        LIMIT ?
        """,
        params,
    ).fetchall()


def run_like_query(
    conn: sqlite3.Connection,
    query: str,
    limit: int,
    source_type: str | None,
) -> list[sqlite3.Row]:
    like = f"%{query.lower()}%"
    params: list[object] = [like, like, like]
    source_filter = ""
    if source_type:
        source_filter = "AND source_type = ?"
        params.append(source_type)
    params.append(limit)

    return conn.execute(
        f"""
        SELECT
          id,
          source_type,
          source_path,
          workspace,
          title,
          999.0 AS score,
          content AS snippet
        FROM records
        WHERE (
          lower(title) LIKE ?
          OR lower(content) LIKE ?
          OR lower(source_path) LIKE ?
        )
        {source_filter}
        ORDER BY
          CASE
            WHEN lower(title) LIKE ? THEN 0
            WHEN lower(source_path) LIKE ? THEN 1
            ELSE 2
          END,
          title ASC
        LIMIT ?
        """,
        [*params[:3], like, like, *params[3:]],
    ).fetchall()


def row_to_result(row: sqlite3.Row, strategy: str, query: str) -> QueryResult:
    snippet = row["snippet"]
    if strategy == "like":
        snippet = plain_snippet(snippet, query)
    return QueryResult(
        id=row["id"],
        source_type=row["source_type"],
        source_path=row["source_path"],
        workspace=row["workspace"],
        title=row["title"],
        score=float(row["score"]),
        snippet=snippet,
        strategy=strategy,
    )
