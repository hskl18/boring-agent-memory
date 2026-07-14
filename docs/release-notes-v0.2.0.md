# Version 0.2.0 Release Notes

Version 0.2.0 makes canonical-first memory useful on repositories that change between full builds.

Markdown now produces deterministic heading-aware chunks with line citations.
Chunk identity is content-addressed, collision-aware for duplicate content, and never reuses an ID for different semantic text after insertion, deletion, split, or merge operations.
`bam update` applies additions, modifications, unique moves, and removals in one transaction, while `--dry-run` reports exact planned paths through a read-only connection.
Schema migrations, full builds, and incremental updates preserve the previous queryable index when work fails before commit.
Legacy migration recomputes redacted-content hashes and reports unavailable raw canonical verification until a full rebuild.

BM25 remains the dependency-free default.
An optional local FastEmbed adapter and weighted reciprocal rank fusion are available behind the `embeddings` extra, with no model download unless a caller explicitly permits it.
All embedding-bound titles, headings, chunks, and queries are redacted at the adapter boundary.

Benchmark v2 records raw per-case evidence for whole-document and chunked BM25.
Its logical identity namespace makes raw result IDs reproducible across random temporary workspaces before retrieval and tie-breaking occur.
The committed core snapshot does not run dense or hybrid retrieval and makes no claim about their quality.

The package version now has one authority in `pyproject.toml`.
Runtime `__version__` and `bam --version` derive from installed metadata.

This release preparation does not merge, tag, publish, or create a GitHub Release.
