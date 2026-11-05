# Boring Agent Memory

[![tests](https://github.com/hskl18/boring-agent-memory/actions/workflows/tests.yml/badge.svg)](https://github.com/hskl18/boring-agent-memory/actions/workflows/tests.yml)

Local BM25 recall over the files your agent already trusts, with line citations and a check that each source still matches what was indexed.

**Status: alpha.** The CLI, Python API, and index schema may still change before 1.0.

Most agent memory failures are not failures of semantic search.
They are failures of trust: stale state, missing provenance, private data captured by default, and memory overriding the source of truth.

Boring Agent Memory indexes the docs, skills, runbooks, bug logs, and ADRs you choose with SQLite FTS5.
It returns source paths and snippets, and your agent reads the cited file before it acts.
It needs no hosted service, embedding API, vector database, model download, or account.

## Install

```bash
python -m pip install boring-agent-memory
```

## Try It

```bash
mkdir notes
printf '# Deploys\n\nRoll back database migrations within 15 minutes.\n' > notes/deploys.md

bam build --include notes
bam query "roll back migrations"
```

```text
deploys.md  score=-3e-06
  /path/to/notes/deploys.md
  # Deploys

[Roll] [back] database [migrations] within 15 minutes.
```

Now change the file and check whether the index still matches it:

```bash
printf '# Deploys\n\nRoll back within 30 minutes.\n' > notes/deploys.md

bam inspect notes/deploys.md
bam update --include notes
```

`bam inspect` reports `content_hash_match: False` until `bam update` picks up the edit.

## Use Your Own Files

Point a config at the files you trust and save it as `memory.yaml`:

```yaml
index_path: ~/.bam/memory.db
source_type: canonical_file
workspace: ~/project/app

include:
  - ~/agent/skills
  - ~/project/*/docs

exclude:
  - "**/secrets/**"
```

```bash
bam build --config memory.yaml --json
bam update --config memory.yaml --dry-run --json
bam update --config memory.yaml --json

bam --db ~/.bam/memory.db query "rollback policy" --limit 5 --json
bam --db ~/.bam/memory.db query "rollback policy" --workspace ~/project/app --json
bam --db ~/.bam/memory.db inspect ~/agent/skills/deployments.md --json
```

`--workspace` matches the exact `workspace` recorded at build time.
A database that does not exist is an error, so a mistyped path cannot look like an empty memory.

## Use It From An Agent

Python:

```python
from boring_agent_memory import memory_query

results = memory_query(
    "rollback policy for database migrations",
    limit=5,
    source_type="canonical_file",
    db_path="~/.bam/memory.db",
)

for result in results:
    print(result.citation)
    print(result.snippet)
```

Any process, as JSON lines over stdio:

```bash
bam --db ~/.bam/memory.db serve --stdio
```

```json
{"query":"rollback policy for database migrations","limit":5,"source_type":"canonical_file"}
{"ok":true,"query":"rollback policy for database migrations","results":[...]}
```

Agent instructions to copy are in [docs/agent-prompt.md](https://github.com/hskl18/boring-agent-memory/blob/main/docs/agent-prompt.md), with setups for [Claude Code](https://github.com/hskl18/boring-agent-memory/blob/main/examples/claude_code.md), [Codex](https://github.com/hskl18/boring-agent-memory/blob/main/examples/codex.md), and [Hermes](https://github.com/hskl18/boring-agent-memory/blob/main/docs/hermes-integration.md).

## Why BM25 First

- Workflow rules contain exact terms, paths, field names, and errors that lexical search finds directly.
- Results are deterministic and debuggable, and rebuilds are reproducible from the source files.
- No embedding model has to see private notes before the first useful result.

An optional local adapter supports controlled dense and hybrid evaluation, but BM25 is the default.

## Evidence

Benchmark v2 compares whole-document and chunked BM25 with raw per-case results:

| Strategy | Recall@1 | Recall@3 | Evidence Recall@1 | Evidence Recall@3 | Privacy leaks |
| --- | ---: | ---: | ---: | ---: | ---: |
| Whole-document BM25 | 0.9091 | 1.0000 | 0.0000 | 0.0000 | 0 |
| Chunked BM25 | 1.0000 | 1.0000 | 1.0000 | 1.0000 | 0 |
| Dense | not run | not run | not run | not run | not run |
| Hybrid RRF | not run | not run | not run | not run | not run |

These are deterministic synthetic fixture results, not production traffic or a broad semantic-memory claim.
See [docs/benchmark-v2.md](https://github.com/hskl18/boring-agent-memory/blob/main/docs/benchmark-v2.md) and [docs/evaluation.md](https://github.com/hskl18/boring-agent-memory/blob/main/docs/evaluation.md).

## What It Is Not

- Not a chatbot brain or an auto-capture memory system. It indexes only paths you name.
- Not a replacement for semantic search over vague queries.
- Not an authority over current files. Canonical files come first, BM25 recall second, model memory last.
- Not a hosted service or a vector database.

## Privacy

Secret-bearing paths such as `.env`, key files, `.git`, and `secrets` folders are skipped by default.
Common API keys, private key blocks, bearer tokens, and `PASSWORD` or `TOKEN` style assignments are redacted before indexing.
These filters are guardrails, not a formal secret scanner, so do not include raw inboxes, browser profiles, credential stores, or unsanitized transcripts.
See [docs/privacy-model.md](https://github.com/hskl18/boring-agent-memory/blob/main/docs/privacy-model.md).

## Documentation

- [CLI reference](https://github.com/hskl18/boring-agent-memory/blob/main/docs/cli.md)
- [Configuration](https://github.com/hskl18/boring-agent-memory/blob/main/docs/configuration.md)
- [Python API](https://github.com/hskl18/boring-agent-memory/blob/main/docs/python-api.md)
- [Architecture](https://github.com/hskl18/boring-agent-memory/blob/main/docs/architecture.md)
- [Comparison with other memory tools](https://github.com/hskl18/boring-agent-memory/blob/main/docs/comparison.md)
- [Status and known limits](https://github.com/hskl18/boring-agent-memory/blob/main/docs/status-and-gaps.md)
- [Roadmap](https://github.com/hskl18/boring-agent-memory/blob/main/docs/roadmap.md)

## Contributing

See [CONTRIBUTING.md](https://github.com/hskl18/boring-agent-memory/blob/main/CONTRIBUTING.md), and read [SECURITY.md](https://github.com/hskl18/boring-agent-memory/blob/main/SECURITY.md) before sharing logs, configs, or memory fixtures.

## License

MIT
