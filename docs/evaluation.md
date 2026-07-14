# Evaluation

Boring Agent Memory keeps two separate evidence surfaces.
The seven-case regression eval protects stable product behavior on every pull request.
Benchmark v2 compares whole-document and chunked BM25 with committed raw case rows and optional local dense and hybrid slots.

Neither surface uses a hosted service, paid API, or LLM judge.

## Regression Eval

The regression fixture covers canonical rules, punctuation-heavy routes, secret redaction, stale-source detection, and source verification.

```bash
bam eval --json \
  --min-recall-at-1 1.0 \
  --min-recall-at-3 1.0 \
  --min-source-accuracy 1.0 \
  --min-snippet-term-rate 1.0 \
  --min-stale-detection-rate 1.0 \
  --max-privacy-leaks 0
```

Current regression baseline:

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

## Benchmark v2

```bash
PYTHONPATH=src python scripts/run_benchmark_v2.py \
  --check \
  --output benchmarks/v2/results/python-3.14-macos-arm64.json
```

The benchmark records every evaluated case and its top results.
Summary metrics can therefore be regenerated from the raw rows without rerunning retrieval.
It records corpus and case hashes, environment metadata, per-strategy index configuration, build time, query latency, index size, source rank, evidence rank, stale-conflict accuracy, and privacy leaks.
Raw result identities use a stable logical benchmark namespace and therefore reproduce across random temporary workspaces.
Timing, index size, and environment metadata remain run-specific.

The adversarial corpus covers embedded synthetic secrets, stale canonical conflicts, duplicate headings with exact line spans, vague paraphrases, code symbols, and a negative query.
The incremental scenario separately covers heading edits, renames, and removal.

See [benchmark-v2.md](benchmark-v2.md) for results and evidence limits.

## Optional Dense and Hybrid Evaluation

Install the optional runtime only when needed:

```bash
python -m pip install -e '.[embeddings]'
```

The no-download path requires an explicit model directory:

```bash
PYTHONPATH=src python scripts/run_benchmark_v2.py \
  --embedding-model BAAI/bge-small-en-v1.5 \
  --embedding-model-path /path/to/local/model \
  --output /tmp/benchmark-v2-hybrid.json
```

Remote model acquisition requires the additional explicit `--allow-model-download` flag.
Dense and hybrid results remain `not_run` in the committed core snapshot because no model was installed or downloaded for the default verification.
No dense or hybrid quality claim is made without committed raw evidence and a recorded model environment.
