# Hermes Integration

This guide shows how to use Boring Agent Memory as a local Hermes-style memory layer.

The intended loop is:

```text
trusted Hermes files
-> bam build --config memory.yaml
-> memory_query(query, limit=3-5)
-> read the cited canonical file
-> answer or act
```

## 1. Install

From this repo:

```bash
python -m venv .venv
. .venv/bin/activate
python -m pip install -e .
```

Check the CLI:

```bash
bam health --json
```

## 2. Create A Hermes Config

Start with:

```bash
cp examples/hermes_memory.yaml memory.yaml
```

Edit `memory.yaml` so `include` points only at trusted canonical files. A typical local agent setup looks like:

```yaml
index_path: ~/.bam/hermes-memory.db
source_type: hermes_file

include:
  - ~/.hermes/skills
  - ~/.hermes/bug-log.md
  - ~/.hermes/reports/sanitized
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

Do not include raw inbox exports, browser profiles, raw terminal logs, auth files, or unsanitized transcripts.

## 3. Build The Index

```bash
bam build --config memory.yaml --json
```

Expected shape:

```json
{
  "database": "/Users/you/.bam/hermes-memory.db",
  "indexed": 120,
  "skipped": 4
}
```

## 4. Query It Manually

```bash
bam --db ~/.bam/hermes-memory.db query "Workday postingAvailable false" --limit 5 --json
```

Each result returns a source path, title, source type, BM25 score, snippet, and strategy.

## 5. Wire It Into An Agent

The smallest Python surface is:

```python
from boring_agent_memory import memory_query

results = memory_query(
    "Workday postingAvailable false",
    limit=5,
    source_type="hermes_file",
    db_path="~/.bam/hermes-memory.db",
)
```

For process-based agents, run:

```bash
bam --db ~/.bam/hermes-memory.db serve --stdio
```

Then send JSON lines:

```json
{"query":"Workday postingAvailable false","limit":5,"source_type":"hermes_file"}
```

## 6. Agent Operating Rule

The agent must treat Boring Agent Memory as recall, not truth.

When a result matters, the agent should:

1. Use the snippet to identify the likely source.
2. Read the cited `source_path`.
3. Prefer the current file or live system over the indexed snippet.
4. Mention when an answer relies on memory recall.

Use [agent-prompt.md](agent-prompt.md) as the full instruction block.

## 7. Verify Staleness

Check whether an indexed source still matches disk:

```bash
bam --db ~/.bam/hermes-memory.db inspect ~/.hermes/skills/job-workflow/SKILL.md --json
```

If `content_hash_match` is false or `verification_available` is false, rebuild:

```bash
bam build --config memory.yaml
```

## 8. Local Demo

Run the built-in demo without touching your real Hermes files:

```bash
python scripts/demo_hermes_layer.py
```

The script creates temporary trusted files, builds an index, queries it, and verifies the cited canonical source.
