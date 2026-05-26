# Release Checklist

Use this before cutting a release.

## Local Checks

```bash
PYTHONPATH=src python -m unittest discover -s tests
python scripts/repo_score.py
python -m pip install -e . --dry-run
```

Optional packaging check:

```bash
python -m pip install build
python -m build
```

## Public Hygiene

- Confirm `.env`, keys, local databases, and generated caches are absent.
- Search for temporary, example, or private URLs before publishing.
- Search for private paths or user-specific secrets.
- Confirm README says what the project is, what it is not, and how to run it.
- Confirm docs explain that recall does not override canonical truth.
- Confirm tests pass on a clean checkout.

## First Public Repository Setup

Only after creating the target GitHub repository:

```bash
git init
git add .
git commit -m "Initial Boring Agent Memory release"
git branch -M main
git remote add origin git@github.com:<owner>/boring-agent-memory.git
git push -u origin main
```
