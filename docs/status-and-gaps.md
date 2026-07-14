# Project Status

Boring Agent Memory 0.2.0 is working canonical-memory infrastructure for local agents.

```text
trusted files -> deterministic chunks -> SQLite FTS5/BM25 -> line citation -> canonical verification
```

## Current Capabilities

- Versioned schema 2 with transactional legacy migration.
- Deterministic document and chunk identifiers.
- Heading-aware Markdown chunking with duplicate-heading and Unicode support.
- Preserved fenced code, list, block quote, and table blocks.
- Source path, heading ancestry, line span, chunk ID, and citation in every query result.
- Atomic full builds and incremental updates.
- Dry-run reports for additions, modifications, unique moves, and removals.
- Configuration fingerprints that prevent unsafe incremental drift.
- Raw source hashes for exact change and move detection.
- Redacted content hashes for indexed payload verification.
- Explicit include paths, workspace filters, and privacy exclusions.
- Optional FastEmbed adapter with a strict no-download default.
- Weighted reciprocal rank fusion for controlled hybrid evaluation.
- Seven-case strict regression gates.
- Benchmark v1 retained as the larger historical lexical baseline.
- Benchmark v2 with raw per-case evidence for whole-document and chunked BM25.
- CLI, Python API, and JSON-lines stdio interfaces.

## Verified Commands

```bash
PYTHONPATH=src python -m unittest discover -s tests
python scripts/repo_score.py
PYTHONPATH=src python scripts/run_incremental_scenario.py
PYTHONPATH=src python scripts/run_benchmark_v1.py --check --output /tmp/benchmark-v1.json
PYTHONPATH=src python scripts/run_benchmark_v2.py --check --output /tmp/benchmark-v2.json
python -m build
python -m twine check dist/*
bam --version
```

## Evidence Boundary

The committed benchmark v2 snapshot runs whole-document and chunked BM25 only.
Dense and hybrid are implemented but remain `not_run` because the default verification did not install or download an embedding model.
The 12-query adversarial corpus is a deterministic engineering fixture, not a production workload or a broad semantic-memory benchmark.
Benchmark v1 remains a larger synthetic lexical comparison, but it is also not production evidence.

## Current Limits

- No file watcher runs automatically.
- Optional dense vectors are built in memory for evaluation and are not persisted in SQLite.
- The stdio interface is not a formal MCP server.
- Protected Markdown blocks may exceed the preferred chunk-size bound.
- Migrated legacy indexes use the old redacted hash as the best available source hash until the next full build.
- Privacy filters are guardrails, not a formal secret scanner.
- Real sanitized workload evidence and user-centered retrieval error analysis remain future work.
