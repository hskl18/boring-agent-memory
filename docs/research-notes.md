# Research Notes

These notes capture implementation choices checked against primary sources.

## SQLite FTS5

SQLite FTS5 supports BM25 ranking, snippets, boolean query operators, tokenizers, prefix queries, and special index maintenance commands. BAM uses FTS5/BM25 for lexical retrieval, `snippet()` for source-grounded previews, and the FTS5 `rank` path for weighted ranking. See the [SQLite FTS5 documentation](https://www.sqlite.org/fts5.html).

Privacy-sensitive rebuilds also enable SQLite `secure_delete` and attempt FTS5 `secure-delete` where the runtime SQLite version supports it. Older SQLite versions continue to work without the FTS5 option.

## Python Packaging

The project metadata uses `pyproject.toml`, SPDX-style license metadata, `license-files`, and an environment-marked dependency for `tomli` on Python versions before 3.11. See the [Python Packaging User Guide](https://packaging.python.org/en/latest/guides/writing-pyproject-toml/).

## GitHub Actions

The CI workflow uses read-only `contents` permissions and `fail-fast: false` for the Python version matrix. This keeps token permissions narrow and reports all version failures instead of canceling the remaining matrix jobs after the first failure. See the [GitHub Actions workflow syntax documentation](https://docs.github.com/en/actions/reference/workflows-and-actions/workflow-syntax).

## OpenSSF

The repository is structured so it can later add OpenSSF Scorecard or a Best Practices badge without changing the package design. The current project already includes standard open-source files such as `SECURITY.md`, `CONTRIBUTING.md`, issue templates, a CI workflow, and a changelog. See [OpenSSF Best Practices](https://best.openssf.org/) and the [Scorecard GitHub Action](https://github.com/ossf/scorecard-action).
