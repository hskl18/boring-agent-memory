# Benchmark v2

Benchmark v2 is a small adversarial engineering fixture for the 0.2.0 retrieval pipeline.
It compares whole-document BM25 and heading-aware chunked BM25 through the same schema, redaction, indexing, and query code.

## Corpus

The corpus contains 7 documents and 12 cases.
It covers duplicate headings with exact line spans, code symbols, embedded synthetic secrets, stale canonical conflicts, vague paraphrases, and a negative no-answer query.
A separate mutation manifest and executable scenario cover one heading edit, one rename, and one removal.

All values are synthetic.
The corpus contains no user messages, credentials, inboxes, browser data, or production records.

## Strategies

- `whole_document_bm25` sets chunk size to `0` and emits one chunk per file.
- `chunked_bm25` uses the default heading-aware chunker at 1600 characters.
- `exact_phrase_grep` is a literal reference baseline.
- `dense` requires an explicit local embedding adapter.
- `hybrid_rrf` combines chunked BM25 and dense ranks with weighted reciprocal rank fusion.

## Metrics

Source Recall@K and MRR measure expected-file retrieval.
Evidence Recall@K additionally requires the expected heading and, when specified, the exact source line span.
The report also includes no-answer precision, stale-conflict accuracy, privacy leaks, build time, median and p95 query latency, index size, and every raw result identity.

## Core Snapshot

The verified core snapshot was produced on Python 3.14.3, SQLite 3.51.3, and macOS arm64.
Latency is descriptive and is not a CI threshold.

| Strategy | Recall@1 | Recall@3 | Evidence Recall@1 | Evidence Recall@3 | MRR | No-answer | Stale conflict | Privacy leaks |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Whole-document BM25 | 0.9091 | 1.0000 | 0.0000 | 0.0000 | 0.9545 | 1.0000 | 1.0000 | 0 |
| Chunked BM25 | 1.0000 | 1.0000 | 1.0000 | 1.0000 | 1.0000 | 1.0000 | 1.0000 | 0 |
| Dense | not run | not run | not run | not run | not run | not run | not run | not run |
| Hybrid RRF | not run | not run | not run | not run | not run | not run | not run | not run |

Whole-document evidence recall is zero because whole-document chunks do not expose heading-level evidence.
This is expected and is the reason the benchmark separates source recall from evidence recall.

## Reproduce

```bash
PYTHONPATH=src python scripts/run_benchmark_v2.py \
  --check \
  --output /tmp/benchmark-v2.json
```

```bash
PYTHONPATH=src python scripts/run_incremental_scenario.py
```

The committed JSON snapshot contains all raw cases, environment metadata, corpus hashes, and path-normalized configuration fingerprints.
Benchmark indexing uses a stable logical identity namespace before retrieval, so raw document and chunk identities do not depend on the random temporary workspace and cannot perturb tie-breaking.
Benchmark fingerprints replace the temporary workspace with a stable placeholder so identical runs reproduce across checkout locations.
The stable raw cases, corpus hashes, and normalized configuration are reproducible, while timing, file size, and environment fields remain descriptive and can differ between runs.

## Evidence Limit

The corpus is intentionally small and adversarial.
Its result is evidence that the tested implementation handles these fixtures, not evidence of production retrieval quality or broad semantic-memory performance.
Dense and hybrid remain `not_run` because the core verification used no optional model and permitted no model download.
