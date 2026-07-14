from __future__ import annotations

import fnmatch
import re
from pathlib import Path


REDACTION_VERSION = 2


DEFAULT_EXCLUDE_GLOBS = (
    "**/.git/**",
    "**/__pycache__/**",
    "**/.pytest_cache/**",
    "**/.mypy_cache/**",
    "**/.ruff_cache/**",
    "**/node_modules/**",
    "**/.venv/**",
    "**/.env",
    "**/.env.*",
    "**/secrets/**",
    "**/*secret*/**",
    "**/*.pem",
    "**/*.key",
    "**/id_rsa",
    "**/id_ed25519",
    "**/.DS_Store",
)


SECRET_PATTERNS = (
    re.compile(r"sk-[A-Za-z0-9_-]{20,}"),
    re.compile(r"github_pat_[A-Za-z0-9_]{20,}"),
    re.compile(r"ghp_[A-Za-z0-9_]{20,}"),
    re.compile(r"AKIA[0-9A-Z]{16}"),
    re.compile(r"(?i)bearer\s+[A-Za-z0-9._~+/=-]{20,}"),
    re.compile(
        r"-----BEGIN [A-Z ]*PRIVATE KEY-----.*?-----END [A-Z ]*PRIVATE KEY-----",
        re.DOTALL,
    ),
    re.compile(
        r"(?im)^([A-Z0-9_]*(?:SECRET|TOKEN|PASSWORD|API_KEY|PRIVATE_KEY)[A-Z0-9_]*\s*=\s*).+$"
    ),
)


def normalized_path(path: Path) -> str:
    return path.expanduser().resolve().as_posix()


def should_exclude_path(
    path: Path,
    root: Path | None = None,
    exclude_globs: list[str] | tuple[str, ...] = (),
) -> bool:
    absolute = normalized_path(path)
    candidates = [absolute, path.as_posix()]
    if root is not None:
        try:
            candidates.append(path.resolve().relative_to(root.resolve()).as_posix())
        except ValueError:
            pass

    for pattern in (*DEFAULT_EXCLUDE_GLOBS, *exclude_globs):
        expanded = str(Path(pattern).expanduser()) if pattern.startswith("~") else pattern
        if any(fnmatch.fnmatch(candidate, expanded) for candidate in candidates):
            return True
    return False


def redact_secrets(content: str) -> tuple[str, int]:
    redactions = 0
    redacted = content
    for pattern in SECRET_PATTERNS:
        redacted, count = pattern.subn(_replacement, redacted)
        redactions += count
    return redacted, redactions


def _replacement(match: re.Match[str]) -> str:
    if match.lastindex:
        replacement = f"{match.group(1)}[REDACTED]"
    else:
        replacement = "[REDACTED]"
    return replacement + ("\n" * match.group(0).count("\n"))
