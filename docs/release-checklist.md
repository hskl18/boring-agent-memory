# Release Checklist

Run this before tagging a release. GitHub Releases are the changelog.

## Clean Installation

```bash
python -m venv /tmp/bam-release-venv
/tmp/bam-release-venv/bin/python -m pip install -e .
/tmp/bam-release-venv/bin/bam --version
```

The version must match `pyproject.toml` package metadata.

## Core Verification

```bash
PYTHONPATH=src python -m unittest discover -s tests
ruff check --target-version py311 src tests scripts
mypy src/boring_agent_memory
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

Run the tests on Python 3.11 and on the newest Python as well, because CI covers only 3.14.
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
Install the wheel into a clean environment outside the repository and run the README's Try It commands.

## Pull Request Gate

- Confirm the feature branch is based on current remote `main`.
- Confirm only intended files are committed.
- Confirm the pull request targets `main`.
- Wait for every GitHub check to finish.
- Record any external blocker in the pull request.

## Publishing

- Before the first release only, add a pending publisher on PyPI for project `boring-agent-memory`: owner `hskl18`, repository `boring-agent-memory`, workflow `publish.yml`, environment `pypi`.
- Tag the merge commit as `vX.Y.Z` and create a GitHub Release with notes.
- Publishing the release runs `.github/workflows/publish.yml`, which builds from the tag and uploads to PyPI through trusted publishing, so no token is stored.
- The workflow refuses to upload when the tag does not match the `pyproject.toml` version, so the tag and the uploaded files always name the same version; PyPI never accepts a file name again, even after deletion.
