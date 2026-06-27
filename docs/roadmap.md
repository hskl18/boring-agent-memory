# Roadmap

This roadmap prioritizes product reliability over platform breadth.

## 0.1.x

- Add heading-aware Markdown chunking.
- Improve config validation errors.
- Add a stable JSON schema document for CLI and stdio responses.

## 0.2.x

- Add incremental update mode.
- Track removed files without requiring a full rebuild.
- Add an optional file watcher.
- Add a formal MCP-compatible single-tool server if users need it.

## Later

- Optional local embedding fallback after BM25.
- Optional graph layer for explicit source-derived relationships.
- Privacy leak test suite with synthetic secrets.
- Larger retrieval benchmark with more fixture domains and baseline comparisons.

## Non-Goals

- hosted vector database by default
- automatic capture of all chats or tool output
- treating memory as authoritative state
- large tool surfaces that expand agent context unnecessarily
