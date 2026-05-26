# Boring Agent Memory

Local-first memory retrieval for agents that should remember source-grounded facts, not vibes.

Boring Agent Memory indexes trusted local files into SQLite FTS5/BM25 and gives agents a small `memory_query()` interface. Query results include source paths and snippets, so the agent can read the canonical file before answering or acting.

It is for agent builders who want durable recall without auto-capturing every chat, sending private notes to a hosted vector database, or letting stale memory override current files.

## Why This Exists

Agents often forget project rules, workflow decisions, bug fixes, and operating constraints. Many memory systems solve that by capturing everything or storing vague summaries as if they were truth. That creates privacy risk, stale state, and noisy prompts.

Boring Agent Memory takes the opposite approach:

```text
trusted local files
-> local SQLite FTS5 / BM25 index
-> source-grounded snippets
-> agent reads the cited file
-> answer or action
```

Canonical files are the docs, skills, logs, ledgers, and reports you already trust as the source of truth. The index is only a recall layer over those files.

## What It Does

- Indexes explicit local files and directories.
- Ranks results with SQLite FTS5/BM25.
- Returns `source_path`, `title`, `source_type`, `score`, and `snippet`.
- Provides CLI, Python API, and JSON-lines stdio interfaces.
- Redacts common secret patterns before indexing.
- Skips common secret-bearing paths by default.
- Lets you inspect whether an indexed source is stale.
- Requires no hosted service, embedding API, vector database, or account.

## What It Is Not

- not a chatbot brain
- not an auto-capture memory system
- not a vector database
- not a hosted service
- not an authority over current files
- not a replacement for reading source documents

The rule is:

```text
Canonical files first. BM25 recall second. Model memory last.
```

## 60-Second Demo

Run the self-contained demo:

```bash
PYTHONPATH=src python scripts/demo_hermes_layer.py
```

It creates temporary trusted files, builds a local index, queries for a workflow rule, and verifies that the cited source file still matches the indexed content.

Example output shape:

```json
{
  "build": {
    "indexed": 2,
    "skipped": 0
  },
  "query_results": [
    {
      "source_type": "hermes_file",
      "source_path": "/tmp/.../skills/job-scout.md",
      "title": "job-scout.md",
      "snippet": "...postingAvailable:false are expired..."
    }
  ],
  "canonical_verification": {
    "indexed": true,
    "exists": true,
    "content_hash_match": true
  }
}
```

## Install

```bash
python -m venv .venv
. .venv/bin/activate
python -m pip install -e .
```

Check the installation:

```bash
bam health --json
```

## Quick Start With Your Files

Create a config:

```bash
cp examples/hermes_memory.yaml memory.yaml
```

Edit `memory.yaml` so `include` points at files you trust:

```yaml
index_path: ~/.bam/agent-memory.db
source_type: canonical_file

include:
  - ~/agent/skills
  - ~/agent/bug-log.md
  - ~/agent/reports/sanitized
  - ~/project/*/docs

exclude:
  - "**/.env"
  - "**/secrets/**"
  - "**/auth.json"
  - "**/*.sqlite"

privacy:
  redact_secrets: true
  max_file_size_kb: 512
```

Build the index:

```bash
bam build --config memory.yaml --json
```

Query it:

```bash
bam --db ~/.bam/agent-memory.db query "rollback policy for database migrations" --limit 5 --json
```

Inspect whether a cited source is stale:

```bash
bam --db ~/.bam/agent-memory.db inspect ~/agent/skills/deployments.md --json
```

## Use It From An Agent

Python API:

```python
from boring_agent_memory import memory_query

results = memory_query(
    "rollback policy for database migrations",
    limit=5,
    source_type="canonical_file",
    db_path="~/.bam/agent-memory.db",
)

for result in results:
    print(result.source_path)
    print(result.snippet)
```

Process API:

```bash
bam --db ~/.bam/agent-memory.db serve --stdio
```

Send JSON lines:

```json
{"query":"rollback policy for database migrations","limit":5,"source_type":"canonical_file"}
```

The response is a JSON line:

```json
{"ok":true,"query":"rollback policy for database migrations","results":[...]}
```

Copy [examples/hermes_agent_instructions.md](examples/hermes_agent_instructions.md) into your agent instructions, or use the fuller [docs/agent-prompt.md](docs/agent-prompt.md).

## CLI

```text
bam init
bam build --config memory.yaml
bam build --include PATH [--include PATH ...] [--exclude GLOB ...]
bam query QUERY [--limit N] [--source-type TYPE] [--json]
bam status [--json]
bam health [--json]
bam inspect [SOURCE_PATH] [--json]
bam serve --stdio
```

The default database path is `.bam/memory.db`.

## Privacy Model

Boring Agent Memory indexes only paths you explicitly include. It skips common secret-bearing paths such as `.env`, key files, `.git`, and `secrets` folders, and it redacts common API keys, private key blocks, bearer tokens, and `PASSWORD` / `TOKEN` / `SECRET` style assignments.

These filters are guardrails, not a formal secret scanner. Do not include raw inboxes, raw browser profiles, credential stores, auth files, or unsanitized transcripts.

See [docs/privacy-model.md](docs/privacy-model.md).

## Common Use Cases

- Give a coding agent recall over project conventions and ADRs.
- Let an operations agent find runbook rules without loading every runbook into context.
- Search sanitized agent reports and bug logs from local files.
- Keep user preferences and workflow rules in source-controlled docs instead of model memory.
- Build a Hermes-style local memory layer for an existing personal agent workflow.

## Documentation

- [Hermes-style integration](docs/hermes-integration.md)
- [CLI reference](docs/cli.md)
- [Configuration reference](docs/configuration.md)
- [Python API](docs/python-api.md)
- [Architecture](docs/architecture.md)
- [Privacy model](docs/privacy-model.md)
- [Canonical-first memory](docs/canonical-first-memory.md)
- [Roadmap](docs/roadmap.md)

## Project Status

Boring Agent Memory currently provides:

- local SQLite FTS5 index
- BM25 ranking
- config-file build
- source-grounded snippets
- privacy filters
- canonical staleness inspection
- Python `memory_query()` API
- JSON-lines stdio agent interface
- docs and examples for Hermes-style, Codex, and Claude Code workflows
- test coverage for CLI, API, config, query, privacy, canonical verification, and demo flow

See [docs/status-and-gaps.md](docs/status-and-gaps.md) for current capabilities and [docs/roadmap.md](docs/roadmap.md) for planned work.

## Contributing

Contributions are welcome. Start with [CONTRIBUTING.md](CONTRIBUTING.md), and read [SECURITY.md](SECURITY.md) before sharing logs, configs, or memory fixtures.

## License

MIT
