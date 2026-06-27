# Deterministic Memory Evals

This directory contains a small local fixture corpus and golden query set for
Boring Agent Memory.

The eval is intentionally deterministic:

- It builds a temporary SQLite FTS5 index from `evals/fixtures`.
- It runs the golden queries in `evals/golden.jsonl`.
- It checks whether expected source files are retrieved.
- It checks whether snippets contain expected terms.
- It checks whether forbidden sources or forbidden token values leak into
  results.
- It can mutate canonical fixture files after indexing to verify stale index
  detection.

Run it from the repository root:

```bash
bam eval --fixtures evals/fixtures --golden evals/golden.jsonl
```

For CI or scripts:

```bash
bam eval --fixtures evals/fixtures --golden evals/golden.jsonl --json
```

Reported metrics:

- `recall_at_1`: expected source is the first result.
- `recall_at_3`: expected source appears in the first three results.
- `mrr`: mean reciprocal rank of the expected source.
- `source_accuracy`: top result is the expected source.
- `snippet_term_rate`: expected terms appear in the matched snippet.
- `privacy_leak_count`: forbidden terms or secret-like strings found in results.
- `stale_detection_rate`: stale forbidden sources do not outrank canonical sources.
  Cases may also mutate a canonical file after indexing and require hash
  mismatch detection before the eval counts the stale case as detected.
