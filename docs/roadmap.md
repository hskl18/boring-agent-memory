# Roadmap

This roadmap prioritizes reliability and evidence over platform breadth.

## Shipped in 0.2.0

- Versioned transactional schema migration.
- Deterministic heading-aware Markdown chunks and line citations.
- Atomic `bam build` and hash-based `bam update`.
- Read-only incremental dry runs with move and removal reporting.
- Optional local FastEmbed adapter and weighted reciprocal rank fusion.
- Evidence-complete benchmark v2 for whole-document and chunked BM25.
- Adversarial retrieval and lifecycle fixtures.
- One authoritative package version.

## Next

- Add an optional file watcher that delegates to the same transactional update path.
- Persist local dense vectors only if a real workflow demonstrates the need.
- Add a formal MCP-compatible single-tool server if interoperability requires it.
- Expand benchmark v2 with independently authored sanitized workloads.
- Add corruption recovery that never mutates canonical sources.

## Non-Goals

- Hosted vector database by default.
- Automatic capture of all chats or tool output.
- Treating memory as authoritative state.
- Large tool surfaces that expand agent context unnecessarily.
