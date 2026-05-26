# Canonical-First Memory

Agent memory should not be magic.

Long-term truth should live in canonical files and ledgers that humans can inspect. Retrieval is useful because it helps the agent find those files quickly. Retrieval is not useful when it silently turns stale conclusions into authority.

Boring Agent Memory therefore treats BM25 recall as context augmentation. If the index disagrees with a workbook, issue tracker, current API, database, config, or source file, the canonical/current source wins.

Good canonical inputs include:

- skills and workflow docs
- project notes
- ADRs
- bug logs
- local ledgers
- configs
- sanitized session summaries

Bad default inputs include:

- raw terminal logs
- raw email bodies
- secrets
- token dumps
- temporary conclusions
- untrusted downloaded files

