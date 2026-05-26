# Roadmap

This roadmap prioritizes product reliability over platform breadth.

## 0.1.x

- Add heading-aware Markdown chunking.
- Add `bam query --workspace`.
- Add package build checks for wheel and sdist.
- Add a small retrieval fixture corpus.
- Add benchmark-style recall tests.
- Improve config validation errors.

## 0.2.x

- Add incremental update mode.
- Track removed files without requiring a full rebuild.
- Add an optional file watcher.
- Add a stable JSON schema for CLI and stdio responses.
- Add a formal MCP-compatible single-tool server if users need it.

## Later

- Optional local embedding fallback after BM25.
- Optional graph layer for explicit source-derived relationships.
- Privacy leak test suite with synthetic secrets.
- Retrieval evaluation harness with recall@k and source accuracy.

## Non-Goals

- hosted vector database by default
- automatic capture of all chats or tool output
- treating memory as authoritative state
- large tool surfaces that expand agent context unnecessarily
