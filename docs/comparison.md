# Comparison

This project is intentionally narrower than full agent memory platforms.

## Boring Agent Memory

- indexes only trusted include paths
- local SQLite FTS5/BM25
- source-grounded snippets
- canonical files remain truth
- small CLI and one query-style server
- no auto-capture by default
- no required vectors or graph

## Bigger Memory Platforms

Projects such as `agentmemory`, `mem0`, and `zep` target broader memory workflows. They can include auto-capture, embeddings, graph memory, viewers, hosted services, MCP-heavy tool surfaces, and multi-agent orchestration.

Those features can be useful, but they are a different product shape. Boring Agent Memory is for users who want predictable local recall over files they already trust.

