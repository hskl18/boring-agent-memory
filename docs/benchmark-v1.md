# Benchmark v1

`benchmark-v1` is a versioned, sanitized synthetic benchmark for the repository's narrow product claim: trusted local files plus source-grounded lexical retrieval can cover a useful class of operational memory.
It is separate from the seven-case strict regression gate.
The regression gate protects known product behavior, while this benchmark makes strategy comparisons and failure boundaries visible.

## Corpus

The committed corpus has 80 documents and 120 queries.
Each category contains 20 queries.

| Category | What it tests |
| --- | --- |
| Exact operational | Current rules expressed with stable operational terms |
| Vague semantic | Looser wording that still shares a few meaningful terms |
| Stale conflict | Canonical documents competing with explicitly historical notes |
| Secret-bearing | Retrieval after secret-shaped values are redacted at ingest |
| Path scoping | Queries that include a repository-like source path |
| Negative no-answer | Queries whose unique terms do not exist in the corpus |

The generator uses fictional codenames and synthetic secret-shaped strings.
It contains no user messages, credentials, inboxes, browser data, or production records.

## Strategies

The BM25 strategy is the production query path: phrase search, token AND, token OR, and the existing LIKE fallback.
The exact phrase grep baseline performs a case-insensitive literal substring search over the same redacted records.
The grep baseline is intentionally simple and establishes how much the tokenized retrieval pipeline adds beyond literal matching.
Embeddings and hybrid retrieval are recorded as `not_run` because no provider-neutral model and cost boundary have been selected.

## Metrics

- Recall@1 and source accuracy measure whether the expected file is first.
- Recall@3 measures whether the expected file appears in the first three results.
- MRR measures the reciprocal rank of the expected file.
- No-answer precision measures whether negative queries return no result.
- Stale conflict accuracy requires the canonical result to outrank any forbidden historical source.
- Privacy leakage counts raw secret-shaped or case-specific forbidden values in returned snippets.
- Rebuild time, index size, median query latency, and p95 query latency describe the local benchmark run.

## Reproduce

Regenerate the deterministic corpus:

```bash
python scripts/generate_benchmark_v1.py
```

Run the benchmark from an installed checkout:

```bash
python scripts/run_benchmark_v1.py --check --output /tmp/benchmark-v1.json
```

From a source checkout without installing:

```bash
PYTHONPATH=src python scripts/run_benchmark_v1.py --check --output /tmp/benchmark-v1.json
```

The checked-in macOS arm64 snapshot is in [`benchmarks/v1/results/python-3.14-macos-arm64.json`](../benchmarks/v1/results/python-3.14-macos-arm64.json).
Latency is environment-specific and is not a CI threshold.
CI gates the corpus size, Recall@3, no-answer precision, and zero privacy leakage instead.

## Current Result

| Strategy | Recall@1 | Recall@3 | MRR | Source accuracy | No-answer precision | Stale conflict | Privacy leaks |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| BM25 | 0.990 | 1.000 | 0.995 | 0.990 | 1.000 | 1.000 | 0 |
| Exact phrase grep | 0.200 | 0.200 | 0.200 | 0.200 | 1.000 | 0.000 | 0 |

On the checked-in Python 3.14.3, SQLite 3.51.3, macOS arm64 snapshot, BM25 rebuilt the 80-document index in 18.680 ms and produced a 163,840-byte SQLite index.
Median BM25 query latency was 0.856 ms and p95 was 1.061 ms.
Exact phrase grep was faster at this small corpus size, but retrieved only 20 percent of positive cases.

## Failure Analysis

BM25 retrieved every expected source within the first three results, but one expected file ranked second, producing Recall@1 and source accuracy of 0.990 rather than 1.000.
This is retained as an honest ranking error rather than changing the fixture after observing the result.
The exact phrase baseline missed 80 of 100 positive queries because the full query did not occur as one literal substring.
Negative no-answer cases are deliberately easy lexical negatives and do not measure adversarial abstention.
The vague category retains meaningful shared terms, so it is not a substitute for a human-authored semantic benchmark.
The stale-conflict cases measure ranking, not automatic truth resolution, and callers must still verify the cited canonical source.

## Scope and Next Evidence

A stronger follow-up should use independently authored queries, a larger and less templated corpus, adversarial no-answer cases, and an explicitly selected local embedding model.
Any embeddings or hybrid result should record model identifier, version, hardware, build time, query latency, index size, and whether text leaves the machine.
Production claims would require real sanitized workloads and user-centered error analysis, neither of which this fixture supplies.

## Index Lifecycle Coverage

The current product performs a full rebuild rather than incremental indexing.
Tests verify that canonical file changes are detected, deleted sources disappear after a rebuild, and a corrupt SQLite file fails without modifying canonical source files.
Automatic corruption recovery and incremental change application remain future work and are not implied by this benchmark.
