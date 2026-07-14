# CLI Reference

The `bam` CLI manages local indexing, incremental updates, querying, inspection, evaluation, and stdio serving.

## Global Options

```text
bam [--db PATH] COMMAND
```

`--db` defaults to `.bam/memory.db`.
Config files can also set `index_path`.

```bash
bam --version
```

The version is derived from installed package metadata.

## init

```bash
bam init --json
```

This creates schema version 2 or transactionally migrates a legacy index.

## build

```bash
bam build --config memory.yaml --json
```

```bash
bam build \
  --include docs \
  --include ~/.agent/skills \
  --exclude "**/.env" \
  --source-type canonical_file \
  --chunk-size 1600 \
  --json
```

`build` scans and chunks candidate files before replacing the complete index in one transaction.
The JSON report includes document, chunk, and skipped-file counts.

## update

```bash
bam update --config memory.yaml --dry-run --json
bam update --config memory.yaml --json
```

`update` compares raw source hashes and reports additions, modifications, unique moves, removals, unchanged documents, and replacement chunk counts.
`--dry-run` opens a checkpointed database in immutable read-only mode and never migrates, writes, or creates SQLite sidecars.
It refuses to run when a non-empty WAL file indicates pending checkpoint work.
An update is rejected when its effective indexing configuration differs from the last full build.

## query

```bash
bam --db ~/.bam/agent-memory.db query "postingAvailable false" --limit 5 --json
bam --db ~/.bam/agent-memory.db query "rollback policy" --workspace ~/project/app --json
```

Results include:

- `id`
- `chunk_id`
- `source_type`
- `source_path`
- `workspace`
- `title`
- `heading`
- `start_line`
- `end_line`
- `citation`
- `score`
- `snippet`
- `strategy`

Use `--workspace` to restrict results to a workspace recorded during indexing.

## inspect

```bash
bam --db ~/.bam/agent-memory.db inspect
bam --db ~/.bam/agent-memory.db inspect /path/to/source.md --json
```

Without a path, `inspect` lists indexed sources.
With a path, it compares the indexed raw source hash to the current file.
For a migrated legacy row, raw hash verification reports unavailable until `bam build` creates a new raw-byte baseline.

## status and health

```bash
bam status --json
bam health --json
```

Status reports schema version, document count, chunk count, source types, and the active configuration fingerprint.
Health also checks SQLite FTS5 availability.

## eval

```bash
bam eval --fixtures evals/fixtures --golden evals/golden.jsonl --json \
  --min-recall-at-1 1.0 \
  --min-source-accuracy 1.0 \
  --max-privacy-leaks 0
```

The command exits non-zero when a configured retrieval, staleness, or privacy gate fails.
`--fixture` remains a compatibility alias for `--fixtures`.

## serve

```bash
bam --db ~/.bam/agent-memory.db serve --stdio
```

The server reads one JSON request per line and returns one JSON response per line.

```json
{"query":"canonical source rule","limit":5,"source_type":"canonical_file","workspace":"~/project/app"}
```
