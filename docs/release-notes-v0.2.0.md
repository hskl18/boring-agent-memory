# Version 0.2.0 Release Notes

Version 0.2.0 makes canonical-first memory useful on repositories that change between full builds.

Markdown now produces deterministic heading-aware chunks with line citations.
`bam update` applies additions, modifications, unique moves, and removals in one transaction, while `--dry-run` reports exact planned paths through a read-only connection.
Schema migrations, full builds, and incremental updates preserve the previous queryable index when work fails before commit.

BM25 remains the dependency-free default.
An optional local FastEmbed adapter and weighted reciprocal rank fusion are available behind the `embeddings` extra, with no model download unless a caller explicitly permits it.

Benchmark v2 records raw per-case evidence for whole-document and chunked BM25.
The committed core snapshot does not run dense or hybrid retrieval and makes no claim about their quality.

The package version now has one authority in `pyproject.toml`.
Runtime `__version__` and `bam --version` derive from installed metadata.

This release preparation does not merge, tag, publish, or create a GitHub Release.
