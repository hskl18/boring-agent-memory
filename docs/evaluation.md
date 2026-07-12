# Evaluation

Boring Agent Memory includes a deterministic eval because the core claim is measurable:

> For many day-to-day agent workflows, BM25 over trusted files can provide enough recall when results are source-grounded and the agent verifies canonical files before acting.

The eval is intentionally local and dependency-light. It does not use an LLM judge, embeddings, or hosted services.

## What It Measures

The fixture corpus covers common memory-layer risks:

- retrieving a canonical workflow rule instead of an older report
- finding source-grounded deployment and browser workflow notes
- handling punctuation-heavy route queries
- redacting secret-shaped fixture values
- keeping stale or historical sources from outranking canonical files
- detecting when an indexed canonical file has changed after the index was built

## Run

```bash
bam eval --json \
  --min-recall-at-1 1.0 \
  --min-recall-at-3 1.0 \
  --min-source-accuracy 1.0 \
  --min-snippet-term-rate 1.0 \
  --min-stale-detection-rate 1.0 \
  --max-privacy-leaks 0
```

From a source checkout without installing:

```bash
PYTHONPATH=src python -m boring_agent_memory.cli eval --json
```

## Metrics

- `recall_at_1`: expected source is the first result.
- `recall_at_3`: expected source appears within the first three results.
- `mrr`: mean reciprocal rank of the expected source.
- `source_accuracy`: top result is the expected source.
- `snippet_term_rate`: snippet/title contain the expected evidence terms.
- `privacy_leak_count`: secret-shaped or forbidden terms found in returned snippets.
- `stale_detection_rate`: stale or historical sources do not outrank canonical sources.

## Quality Gates

`bam eval` can enforce thresholds and return a non-zero exit code when the memory layer regresses:

```bash
bam eval \
  --min-recall-at-1 1.0 \
  --min-source-accuracy 1.0 \
  --max-privacy-leaks 0
```

The JSON output includes:

- `passed`: whether all configured gates passed
- `failures`: human-readable gate failures

The GitHub Actions workflow uses these gates so eval quality is checked on every push.

## Current Fixture Baseline

```text
cases: 7
recall_at_1: 1.000
recall_at_3: 1.000
mrr: 1.000
source_accuracy: 1.000
snippet_term_rate: 1.000
privacy_leak_count: 0
stale_detection_rate: 1.000
```

This is a small regression fixture, not a broad industry benchmark. It is meant to keep the core product behavior honest as the project adds chunking, incremental indexing, and optional retrieval strategies.

For the separate 120-query strategy comparison, see [Benchmark v1](benchmark-v1.md).
