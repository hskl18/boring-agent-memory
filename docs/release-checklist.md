# Release Checklist

This checklist prepares version 0.2.0 without merging, tagging, publishing, or creating a GitHub Release.

## Clean Installation

```bash
python -m venv /tmp/bam-release-venv
/tmp/bam-release-venv/bin/python -m pip install -e .
/tmp/bam-release-venv/bin/bam --version
```

The version must be `bam 0.2.0` and must match `pyproject.toml` package metadata.

## Core Verification

```bash
PYTHONPATH=src python -m unittest discover -s tests
python scripts/repo_score.py
PYTHONPATH=src python -m boring_agent_memory.cli eval --json \
  --min-recall-at-1 1.0 \
  --min-recall-at-3 1.0 \
  --min-source-accuracy 1.0 \
  --min-snippet-term-rate 1.0 \
  --min-stale-detection-rate 1.0 \
  --max-privacy-leaks 0
PYTHONPATH=src python scripts/run_incremental_scenario.py
PYTHONPATH=src python scripts/run_benchmark_v1.py --check --output /tmp/benchmark-v1.json
PYTHONPATH=src python scripts/run_benchmark_v2.py --check --output /tmp/benchmark-v2.json
```

Verify that the incremental scenario reports one modified, one moved, and one removed source.
Verify that the removed source is no longer queryable.
Verify that the process-interruption test leaves the previous index queryable.

## Optional Embedding Verification

Do not install or download a model for the core release gate.
If a reviewed local model is already available, install `.[embeddings]`, pass its explicit local path, and record model identity, dimensions, environment, raw cases, and cleanup.
Do not publish a dense or hybrid quality claim when that evidence is absent.

## Packaging

```bash
python -m pip install build twine
rm -rf build dist
python -m build
python -m twine check dist/*
python -m zipfile -l dist/*.whl
tar -tf dist/*.tar.gz
```

Inspect the wheel and source distribution for secrets, local databases, caches, model files, temporary outputs, and private paths.
Confirm that `CHANGELOG.md` was not manually edited.

## Pull Request Gate

- Confirm the feature branch is based on current remote `main`.
- Confirm only intended files are committed.
- Confirm the pull request targets `main`.
- Wait for every GitHub check to finish.
- Record any external blocker in the pull request.
- Do not merge the pull request.
- Do not create a Git tag or GitHub Release.
