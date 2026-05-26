# Privacy Model

Boring Agent Memory is designed around explicit ingestion, not ambient capture.

## What Is Indexed

Only paths named in config or CLI flags are candidates for indexing:

- skills and workflow notes
- sanitized reports
- bug logs
- project docs and ADRs
- canonical ledgers or summaries

The index stores local source paths, titles, text content, redacted content hashes, metadata, and FTS5 terms in SQLite.

## What Is Not Indexed By Default

The default exclude rules skip common high-risk paths:

- `.env` and `.env.*`
- `secrets/`
- private key files
- `.git/`
- virtualenvs and dependency folders
- cache directories

The text redactor also masks common API keys, bearer tokens, private key blocks, and `SECRET` / `TOKEN` / `PASSWORD` style assignments before content is written to SQLite.

## Guardrail, Not Guarantee

The privacy filter is intentionally conservative, but it is not a formal secret scanner. The primary safety boundary is choosing trusted include paths. Do not point BAM at raw browser profiles, raw email dumps, auth folders, credential stores, or unsanitized transcripts.

## Agent Rule

Agents should treat returned snippets as recall hints only. Before acting on sensitive or current state, they should read the canonical file or live system state directly.
