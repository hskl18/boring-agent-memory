# Comparison

This project is intentionally narrower than full agent memory platforms. Its ambition is different: provide canonical-memory infrastructure for agents that should trust files, verify sources, and keep memory measurable.

The core claim is:

```text
Operational agent memory is often a retrieval problem over trusted files, not a need for a second model-owned brain.
```

## Boring Agent Memory

- indexes only trusted include paths
- local SQLite FTS5/BM25
- source-grounded snippets
- canonical files remain truth
- small CLI and one query-style server
- no auto-capture by default
- no required vectors or graph

## Bigger Memory Platforms

Projects such as `agentmemory`, `mem0`, and `zep` target broader memory workflows. They can include auto-capture, embeddings, graph memory, viewers, hosted services, MCP-heavy tool surfaces, and multi-agent orchestration.

Those features can be useful, but they are a different product shape. Boring Agent Memory is for users who want predictable local recall over files they already trust.

## What This Project Optimizes For

- source provenance over opaque summaries
- deterministic local recall over hosted dependency chains
- canonical verification over memory-as-truth
- measurable eval gates over demo-only claims
- small agent tool surface over broad tool suites

## When To Use BAM

Use Boring Agent Memory when:

- the durable truth already lives in local files
- you want citations, source paths, and snippets
- you do not want automatic capture of every chat or tool output
- you want deterministic rebuilds from trusted sources
- lexical recall is good enough for the workflow
- the agent should verify canonical files before acting

## When To Use A Larger Memory Platform

Use a broader memory platform when you need:

- automatic conversation memory extraction
- managed cloud storage, dashboards, or user-memory APIs
- graph/entity memory
- vector-first semantic recall
- multi-agent orchestration built into the memory product
- hosted persistence and operational tooling

## Decision Table

| Need | Better fit |
| --- | --- |
| Local recall over trusted docs, skills, ADRs, and bug logs | Boring Agent Memory |
| Source-grounded snippets and canonical-file verification | Boring Agent Memory |
| No hosted service or embedding API by default | Boring Agent Memory |
| Automatic conversation memory extraction | A broader memory platform |
| Managed cloud storage, dashboards, or user-memory APIs | A broader memory platform |
| Entity graph memory or semantic vector-first recall | A broader memory platform |

The claim is not that BM25 is always stronger than semantic memory. The claim is that many practical agent memory problems do not need semantic infrastructure first. A small BM25 layer over trusted files is cheaper, easier to audit, and often enough.

## Known Tradeoffs

| Tradeoff | Current answer | Concept-compatible next step |
| --- | --- | --- |
| Vague semantic queries can miss relevant files | BM25-first lexical recall | Optional local semantic fallback after BM25, never authority |
| Whole-file indexing can dilute long documents | Plain text file records | Heading-aware chunks that still cite canonical files |
| Full rebuild is simple but inefficient | Deterministic rebuild | Incremental update mode with content hashes |
| Privacy filters are guardrails | Common redaction patterns and exclude globs | Synthetic privacy leak eval corpus |
| Eval is small | Deterministic regression fixture | Larger public fixture benchmark with baseline comparisons |
