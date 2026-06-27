# Project Status

Boring Agent Memory is a working local-first memory retrieval layer for agents.

It provides a small, auditable path from trusted local files to source-grounded agent recall:

```text
trusted files -> SQLite FTS5/BM25 -> memory_query() -> cited source file -> agent action
```

## Current Capabilities

- Python package named `boring-agent-memory`
- `bam` CLI entrypoint
- local SQLite database initialization
- SQLite FTS5 indexing
- BM25 query ranking over title, content, and source path using SQLite FTS5 rank configuration
- explicit include paths for trusted files
- glob include patterns for trusted file discovery
- default exclude globs for `.env`, keys, secret folders, virtualenvs, git metadata, and common build caches
- content redaction for common API keys, bearer tokens, private key blocks, and `SECRET` / `TOKEN` / `PASSWORD` style assignments
- source-grounded query results with `source_path`, `title`, `source_type`, `score`, `snippet`, and retrieval `strategy`
- JSON output for CLI integration
- YAML, TOML, or JSON config loading via `bam build --config memory.yaml`
- canonical source inspection via `bam inspect [SOURCE_PATH]`
- agent-facing Python API via `memory_query()`
- JSON-lines stdio server via `bam serve --stdio`
- workspace filtering for CLI, Python API, and stdio queries
- deterministic eval fixture via `bam eval`
- examples for Hermes-style, Codex, and Claude Code workflows
- docs for integration, CLI, configuration, architecture, canonical-first memory, privacy, and comparison positioning
- tests for index build, query ranking, privacy filters, CLI, Python API, evals, demo flow, and stdio server

## Verified Commands

```bash
PYTHONPATH=src python -m unittest discover -s tests
python scripts/repo_score.py
PYTHONPATH=src python -m boring_agent_memory.cli eval --json
python -m build
python -m twine check dist/*
```

Latest local result:

```text
Ran the unit test suite
OK

score: 100
failed: []

eval recall_at_1: 1.000
eval privacy_leak_count: 0
```

## Good Fits

Use Boring Agent Memory for:

- local recall over memory notes, skills, ADRs, bug logs, and sanitized summaries
- finding source files with explainable lexical search
- adding agent memory without auto-ingesting raw conversation logs
- privacy-conscious indexing where canonical files remain the source of truth
- debugging retrieval with local SQLite and plain text files

## Current Limits

- `bam build` rebuilds the whole index.
- Removed files are handled by rebuild, not by an incremental watcher.
- Markdown and code are indexed as plain text; there is no heading-aware chunking yet.
- `bam serve --stdio` is JSON-lines, not a full MCP server.
- Privacy filters are guardrails, not a formal secret scanner.
- The included eval fixture is a small regression corpus, not a broad benchmark.

See [roadmap.md](roadmap.md) for planned work.
