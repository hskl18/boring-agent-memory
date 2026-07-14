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
    chunk_id: str
    source_type: str
    source_path: str
    workspace: str
    title: str
    heading: str
    start_line: int
    end_line: int
    citation: str
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
    workspace: Path | str | None = None,
) -> list[QueryResult]:
    conn = connect(db_path)
    init_db(conn)
    try:
        workspace_path = Path(workspace).expanduser().resolve() if workspace else None
        results = _query_memory(conn, query, limit, source_type, workspace_path)
    finally:
        conn.close()
    return results


def _query_memory(
    conn: sqlite3.Connection,
    query: str,
    limit: int,
    source_type: str | None,
    workspace: Path | None,
) -> list[QueryResult]:
    seen_documents: set[str] = set()
    results: list[QueryResult] = []

    for strategy, fts_query in build_fts_queries(query):
        try:
            rows = run_fts_query(conn, fts_query, max(limit * 4, limit), source_type, workspace)
        except sqlite3.DatabaseError:
            continue
        for row in rows:
            if row["id"] in seen_documents:
                continue
            seen_documents.add(row["id"])
            results.append(row_to_result(row, strategy, query))
            if len(results) >= limit:
                return results

    if len(results) < limit:
        rows = run_like_query(
            conn,
            query,
            max((limit - len(results)) * 4, limit),
            source_type,
            workspace,
        )
        for row in rows:
            if row["id"] in seen_documents:
                continue
            seen_documents.add(row["id"])
            results.append(row_to_result(row, "like", query))
            if len(results) >= limit:
                break

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
    workspace: Path | None,
) -> list[sqlite3.Row]:
    params: list[object] = [fts_query]
    source_filter = ""
    if source_type:
        source_filter = "AND d.source_type = ?"
        params.append(source_type)
    workspace_filter = ""
    if workspace:
        workspace_filter = "AND d.workspace = ?"
        params.append(workspace.as_posix())
    params.append(limit)

    return conn.execute(
        f"""
        SELECT
          d.id,
          c.id AS chunk_id,
          d.source_type,
          d.source_path,
          d.workspace,
          d.title,
          c.heading,
          c.start_line,
          c.end_line,
          rank AS score,
          snippet(chunks_fts, 3, '[', ']', '...', 28) AS snippet
        FROM chunks_fts
        JOIN chunks c ON c.id = chunks_fts.chunk_id
        JOIN documents d ON d.id = c.document_id
        WHERE chunks_fts MATCH ?
        AND rank MATCH 'bm25(0.0, 2.5, 1.8, 1.0, 0.25)'
        {source_filter}
        {workspace_filter}
        ORDER BY rank ASC, c.id ASC
        LIMIT ?
        """,
        params,
    ).fetchall()


def run_like_query(
    conn: sqlite3.Connection,
    query: str,
    limit: int,
    source_type: str | None,
    workspace: Path | None,
) -> list[sqlite3.Row]:
    like = f"%{query.lower()}%"
    params: list[object] = [like, like, like, like]
    source_filter = ""
    if source_type:
        source_filter = "AND d.source_type = ?"
        params.append(source_type)
    workspace_filter = ""
    if workspace:
        workspace_filter = "AND d.workspace = ?"
        params.append(workspace.as_posix())
    params.append(limit)

    return conn.execute(
        f"""
        SELECT
          d.id,
          c.id AS chunk_id,
          d.source_type,
          d.source_path,
          d.workspace,
          d.title,
          c.heading,
          c.start_line,
          c.end_line,
          999.0 AS score,
          c.content AS snippet
        FROM chunks c
        JOIN documents d ON d.id = c.document_id
        WHERE (
          lower(d.title) LIKE ?
          OR lower(c.heading) LIKE ?
          OR lower(c.content) LIKE ?
          OR lower(d.source_path) LIKE ?
        )
        {source_filter}
        {workspace_filter}
        ORDER BY
          CASE
            WHEN lower(d.title) LIKE ? THEN 0
            WHEN lower(d.source_path) LIKE ? THEN 1
            ELSE 2
          END,
          d.title ASC,
          c.ordinal ASC
        LIMIT ?
        """,
        [*params[:4], like, like, *params[4:]],
    ).fetchall()


def row_to_result(row: sqlite3.Row, strategy: str, query: str) -> QueryResult:
    snippet = row["snippet"]
    if strategy == "like":
        snippet = plain_snippet(snippet, query)
    heading = row["heading"]
    location = f"L{row['start_line']}-L{row['end_line']}"
    citation = f"{row['source_path']}:{location}"
    if heading:
        citation = f"{row['source_path']}#{heading}:{location}"
    return QueryResult(
        id=row["id"],
        chunk_id=row["chunk_id"],
        source_type=row["source_type"],
        source_path=row["source_path"],
        workspace=row["workspace"],
        title=row["title"],
        heading=heading,
        start_line=int(row["start_line"]),
        end_line=int(row["end_line"]),
        citation=citation,
        score=float(row["score"]),
        snippet=snippet,
        strategy=strategy,
    )
