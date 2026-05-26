## Summary

Describe the change.

## Validation

```bash
PYTHONPATH=src python -m unittest discover -s tests
python scripts/repo_score.py
```

## Checklist

- [ ] Tests cover the changed behavior.
- [ ] Docs are updated for user-visible changes.
- [ ] No generated databases, caches, local secrets, or private files are included.
- [ ] The change preserves canonical-first retrieval semantics.
