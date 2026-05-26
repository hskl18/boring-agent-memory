# Hermes Agent Instructions

You have access to Boring Agent Memory, a local BM25 recall layer over trusted Hermes files.

Use it when prior local context may matter:

- user asks about previous work
- task mentions a known repo, workflow, skill, report, bug, route, or ledger
- a remembered rule could prevent repeating a known mistake
- you need to find the right canonical file before editing

Do not use it for:

- simple one-off tasks
- facts that must be checked live
- mining private raw logs or secrets

Tool contract:

```text
memory_query(query: string, limit?: number, source_type?: string) -> results
```

Workflow:

1. Query with concrete terms from the user request.
2. Read the cited source file before relying on the result.
3. Prefer current canonical files and live state over indexed snippets.
4. Use low limits first, normally 3 to 5.
5. Tell the user when a claim came from memory recall and was not freshly verified.

Core rule:

```text
Canonical files first. BM25 recall second. Model memory last.
```
