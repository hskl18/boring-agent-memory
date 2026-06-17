# CLI Reference

The `bam` CLI manages local indexing, querying, status checks, and stdio serving.

## Global Options

```text
bam [--db PATH] COMMAND
```

`--db` defaults to `.bam/memory.db`. Config files can also set `index_path`.

## init

```bash
bam init
bam init --json
```

Creates the SQLite database and FTS5 tables.

## build

```bash
bam build --config memory.yaml --json
```

or:

```bash
bam build \
  --include docs \
  --include ~/.agent/skills \
  --exclude "**/.env" \
  --exclude "**/secrets/**" \
  --source-type canonical_file \
  --json
```

`build` clears and rebuilds the index from candidate files.

## query

```bash
bam --db ~/.bam/agent-memory.db query "postingAvailable false" --limit 5 --json
bam --db ~/.bam/agent-memory.db query "rollback policy" --workspace ~/project/app --json
```

Results include:

- `id`
- `source_type`
- `source_path`
- `workspace`
- `title`
- `score`
- `snippet`
- `strategy`

Use `--workspace` to restrict results to a workspace recorded during indexing.

## inspect

```bash
bam --db ~/.bam/agent-memory.db inspect
bam --db ~/.bam/agent-memory.db inspect /path/to/source.md --json
```

Without a path, `inspect` lists indexed sources. With a path, it compares the indexed content hash to the current file.

## status

```bash
bam status --json
```

Shows whether the database exists, record count, and source-type counts.

## health

```bash
bam health --json
```

Checks database existence and SQLite FTS5 support.

## serve

```bash
bam --db ~/.bam/agent-memory.db serve --stdio
```

Reads JSON lines from stdin:

```json
{"query":"canonical source rule","limit":5,"source_type":"canonical_file","workspace":"~/project/app"}
```

Writes JSON lines to stdout:

```json
{"ok":true,"query":"canonical source rule","results":[]}
```
