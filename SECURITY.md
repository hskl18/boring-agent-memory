# Security Policy

Boring Agent Memory is local-first, but it can still index sensitive text if configured incorrectly.

## Supported Versions

Security fixes target the latest release.

## Reporting A Vulnerability

Report suspected vulnerabilities privately through [GitHub private vulnerability reporting](https://github.com/hskl18/boring-agent-memory/security/advisories/new).
Do not open a public issue containing secrets, credentials, or private content.

## Sensitive Data Guidance

Do not share:

- `.env` files
- API keys or tokens
- private keys
- raw browser profiles
- raw email exports
- raw terminal logs
- unsanitized transcripts
- local SQLite memory databases that may contain private content

Use synthetic fixtures or sanitized snippets when reporting issues.

## Security Model

The project provides privacy guardrails:

- explicit include paths
- default secret-bearing path excludes
- secret-pattern redaction
- local SQLite storage
- no hosted service dependency

These guardrails are not a formal data-loss-prevention system.
Users are responsible for selecting trusted include paths.
