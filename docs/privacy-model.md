# Privacy Model

Boring Agent Memory is designed around explicit ingestion, not ambient capture.

## What Is Indexed

Only paths named in configuration or CLI flags are candidates for indexing.
The SQLite index stores local source paths, titles, redacted text, raw-byte hashes, redacted-content hashes, metadata, chunk line spans, and FTS5 terms.
Raw source hashes detect exact file changes without storing unredacted content.

## What Is Not Indexed By Default

The default exclusions skip `.env` files, secret directories, private keys, `.git`, dependency directories, virtual environments, and caches.
The content filter masks common API keys, bearer tokens, private key blocks, and assignment lines containing `SECRET`, `TOKEN`, `PASSWORD`, `API_KEY`, or `PRIVATE_KEY` before chunking or persistence.

The same redacted chunk text is the only text passed to an optional embedding adapter.
The adapter is local-only and no-download by default.
This project does not implement a hosted embedding provider.

## Update Diagnostics

Dry-run reports include source paths and operation counts.
They do not emit content, raw hashes, redacted hashes, or secret values.
Dry-run uses a read-only SQLite connection and cannot migrate the index.

## Guardrail, Not Guarantee

The privacy filter is not a formal secret scanner.
The primary safety boundary is choosing trusted include paths.
Do not point BAM at raw browser profiles, raw email dumps, auth folders, credential stores, or unsanitized transcripts.

## Agent Rule

Agents should treat returned snippets as recall hints only.
Before acting on sensitive or current state, they should read the canonical file or live system state directly.
