# Contributing

Thanks for considering a contribution to Boring Agent Memory.

This project values small, auditable changes that preserve the canonical-first memory model.

## Development Setup

```bash
python -m venv .venv
. .venv/bin/activate
python -m pip install -e .
```

## Test

```bash
PYTHONPATH=src python -m unittest discover -s tests
python scripts/repo_score.py
python -m pip install -e . --dry-run
```

## Design Rules

- Keep memory retrieval local-first by default.
- Do not add hosted services or network calls to core retrieval.
- Do not auto-ingest raw conversations, raw tool output, inboxes, browser profiles, or secrets.
- Return source paths and snippets rather than unsupported conclusions.
- Keep the agent-facing tool surface small.
- Treat canonical files as truth and the index as rebuildable recall.

## Pull Request Checklist

- Tests cover the changed behavior.
- Docs are updated for user-visible changes.
- New config fields are documented in `docs/configuration.md`.
- New CLI behavior is documented in `docs/cli.md`.
- Generated files, databases, caches, and local secrets are not included.

## Reporting Bugs

Include:

- operating system
- Python version
- command used
- expected result
- actual result
- minimal sanitized config or fixture

Do not include secrets, raw inboxes, private transcripts, browser profiles, or `.env` files.
