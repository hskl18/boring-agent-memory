from __future__ import annotations

import argparse
import json
import sqlite3
from pathlib import Path

from . import __version__
from .canonical import list_canonical_sources, verify_canonical_source
from .config import load_config
from .index import build_index
from .query import query_memory
from .schema import DEFAULT_DB_PATH, connect, fts5_available, init_db
from .server import serve_stdio


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="bam", description="Boring Agent Memory")
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    parser.add_argument("--db", default=None, help="SQLite database path")
    subparsers = parser.add_subparsers(dest="command", required=True)

    init_parser = subparsers.add_parser("init", help="Initialize the local database")
    init_parser.add_argument("--json", action="store_true")

    build_parser = subparsers.add_parser("build", help="Build a local BM25 index")
    build_parser.add_argument("--config", help="YAML, TOML, or JSON memory config")
    build_parser.add_argument("--include", action="append", default=[], help="File or directory to index")
    build_parser.add_argument("--exclude", action="append", default=[], help="Glob to exclude")
    build_parser.add_argument("--workspace", default=None, help="Workspace root for relative includes")
    build_parser.add_argument("--source-type", default=None)
    build_parser.add_argument("--max-bytes", type=int, default=None)
    build_parser.add_argument("--json", action="store_true")

    query_parser = subparsers.add_parser("query", help="Query the local memory index")
    query_parser.add_argument("query")
    query_parser.add_argument("--limit", type=int, default=5)
    query_parser.add_argument("--source-type", default=None)
    query_parser.add_argument("--workspace", default=None)
    query_parser.add_argument("--json", action="store_true")

    status_parser = subparsers.add_parser("status", help="Show index status")
    status_parser.add_argument("--json", action="store_true")

    inspect_parser = subparsers.add_parser("inspect", help="Inspect indexed canonical sources")
    inspect_parser.add_argument("source_path", nargs="?", help="Canonical source path to verify")
    inspect_parser.add_argument("--limit", type=int, default=50)
    inspect_parser.add_argument("--json", action="store_true")

    health_parser = subparsers.add_parser("health", help="Run local health checks")
    health_parser.add_argument("--json", action="store_true")

    serve_parser = subparsers.add_parser("serve", help="Serve a tiny JSON-lines query interface")
    serve_parser.add_argument("--stdio", action="store_true", help="Read JSON lines from stdin")

    args = parser.parse_args(argv)
    db_path = Path(args.db) if args.db else DEFAULT_DB_PATH

    if args.command == "init":
        conn = connect(db_path)
        init_db(conn)
        ok = fts5_available(conn)
        conn.close()
        return emit({"database": db_path.as_posix(), "fts5": ok}, args.json)

    if args.command == "build":
        config = load_config(args.config) if args.config else None
        db_path = Path(args.db) if args.db else (config.index_path if config else DEFAULT_DB_PATH)
        includes = [*(config.include if config else ()), *args.include]
        excludes = [*(config.exclude if config else ()), *args.exclude]
        workspace = args.workspace or (config.workspace if config else None)
        source_type = args.source_type or (config.source_type if config else "file")
        max_bytes = args.max_bytes or (config.max_bytes if config else 512 * 1024)
        if not includes:
            parser.error("build requires --include or --config with include paths")
        stats = build_index(
            db_path=db_path,
            includes=list(includes),
            excludes=list(excludes),
            workspace=workspace,
            source_type=source_type,
            max_bytes=max_bytes,
        )
        return emit({"database": db_path.as_posix(), **stats}, args.json)

    if args.command == "query":
        results = [
            result.to_dict()
            for result in query_memory(
                db_path=db_path,
                query=args.query,
                limit=args.limit,
                source_type=args.source_type,
                workspace=args.workspace,
            )
        ]
        if args.json:
            print(json.dumps({"query": args.query, "results": results}, indent=2, ensure_ascii=False))
        else:
            print_results(results)
        return 0

    if args.command == "status":
        return emit(status(db_path), args.json)

    if args.command == "inspect":
        if args.source_path:
            return emit(verify_canonical_source(db_path, args.source_path), args.json)
        payload = {
            "database": db_path.as_posix(),
            "sources": list_canonical_sources(db_path, limit=args.limit),
        }
        return emit(payload, args.json)

    if args.command == "health":
        health = status(db_path)
        health["sqlite_fts5"] = _sqlite_fts5_health(db_path)
        health["ok"] = health["sqlite_fts5"] and health["database_exists"]
        return emit(health, args.json)

    if args.command == "serve":
        if not args.stdio:
            parser.error("serve currently requires --stdio")
        return serve_stdio(db_path)

    parser.error("unknown command")
    return 2


def status(db_path: Path) -> dict[str, object]:
    if not db_path.exists():
        return {
            "database": db_path.as_posix(),
            "database_exists": False,
            "records": 0,
            "source_types": {},
        }
    conn = connect(db_path)
    init_db(conn)
    records = conn.execute("SELECT count(*) FROM records").fetchone()[0]
    rows = conn.execute(
        "SELECT source_type, count(*) AS count FROM records GROUP BY source_type ORDER BY source_type"
    ).fetchall()
    conn.close()
    return {
        "database": db_path.as_posix(),
        "database_exists": True,
        "records": records,
        "source_types": {row["source_type"]: row["count"] for row in rows},
    }


def _sqlite_fts5_health(db_path: Path) -> bool:
    conn = connect(db_path)
    try:
        return fts5_available(conn)
    finally:
        conn.close()


def emit(payload: dict[str, object], as_json: bool) -> int:
    if as_json:
        print(json.dumps(payload, indent=2, ensure_ascii=False))
    else:
        for key, value in payload.items():
            print(f"{key}: {value}")
    return 0


def print_results(results: list[dict[str, object]]) -> None:
    for result in results:
        print(f"{result['title']}  score={result['score']}")
        print(f"  {result['source_path']}")
        print(f"  {result['snippet']}")


if __name__ == "__main__":
    raise SystemExit(main())
