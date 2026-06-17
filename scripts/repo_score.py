from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


CHECKS = {
    "readme_public_positioning": ("README.md", "Local-first memory retrieval for agents that should remember source-grounded facts"),
    "license": ("LICENSE", "MIT License"),
    "package_metadata": ("pyproject.toml", "boring-agent-memory"),
    "manifest": ("MANIFEST.in", "recursive-include docs *.md"),
    "cli_entrypoint": ("src/boring_agent_memory/cli.py", "def main"),
    "fts5_schema": ("src/boring_agent_memory/schema.py", "CREATE VIRTUAL TABLE"),
    "privacy_filters": ("src/boring_agent_memory/privacy.py", "DEFAULT_EXCLUDE_GLOBS"),
    "stdio_server": ("src/boring_agent_memory/server.py", "serve_stdio"),
    "python_api": ("src/boring_agent_memory/api.py", "memory_query"),
    "config_loader": ("src/boring_agent_memory/config.py", "load_config"),
    "canonical_inspect": ("src/boring_agent_memory/canonical.py", "verify_canonical_source"),
    "hermes_integration_docs": ("docs/hermes-integration.md", "Hermes Integration"),
    "hermes_agent_instructions": ("examples/hermes_agent_instructions.md", "Canonical files first"),
    "hermes_demo": ("scripts/demo_hermes_layer.py", "source_type=\"hermes_file\""),
    "cli_docs": ("docs/cli.md", "CLI Reference"),
    "config_docs": ("docs/configuration.md", "Configuration"),
    "api_docs": ("docs/python-api.md", "Python API"),
    "roadmap": ("docs/roadmap.md", "Roadmap"),
    "research_notes": ("docs/research-notes.md", "Research Notes"),
    "contributing": ("CONTRIBUTING.md", "Contributing"),
    "security": ("SECURITY.md", "Security Policy"),
    "changelog": ("CHANGELOG.md", "0.1.0 - Unreleased"),
    "issue_template": (".github/ISSUE_TEMPLATE/bug_report.md", "Bug report"),
    "pr_template": (".github/PULL_REQUEST_TEMPLATE.md", "Validation"),
    "architecture_docs": ("docs/architecture.md", "SQLite FTS5"),
    "privacy_docs": ("docs/privacy-model.md", "explicit ingestion"),
    "comparison_docs": ("docs/comparison.md", "no auto-capture"),
    "tests": ("tests/test_cli.py", "serve"),
}


def main() -> int:
    passed = []
    failed = []
    for name, (path, needle) in CHECKS.items():
        file_path = ROOT / path
        if file_path.exists() and needle in file_path.read_text(encoding="utf-8"):
            passed.append(name)
        else:
            failed.append(name)

    score = round((len(passed) / len(CHECKS)) * 100)
    print(
        json.dumps(
            {
                "score": score,
                "passed": passed,
                "failed": failed,
                "note": "Static repo-readiness score; test results are reported separately.",
            },
            indent=2,
        )
    )
    return 0 if not failed else 1


if __name__ == "__main__":
    raise SystemExit(main())
