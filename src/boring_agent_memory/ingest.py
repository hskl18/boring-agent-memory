from __future__ import annotations

import hashlib
import json
from glob import glob
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

from .privacy import redact_secrets, should_exclude_path


TEXT_EXTENSIONS = {
    ".adoc",
    ".cfg",
    ".conf",
    ".csv",
    ".ini",
    ".json",
    ".jsonl",
    ".log",
    ".md",
    ".mdx",
    ".py",
    ".rst",
    ".sql",
    ".toml",
    ".txt",
    ".yaml",
    ".yml",
}


@dataclass(frozen=True)
class IngestedRecord:
    id: str
    source_type: str
    source_path: str
    workspace: str
    title: str
    content: str
    content_hash: str
    metadata_json: str
    updated_at: str


def iter_candidate_files(
    includes: Iterable[str],
    excludes: Iterable[str] = (),
    workspace: Path | None = None,
) -> list[Path]:
    root = (workspace or Path.cwd()).expanduser().resolve()
    files: list[Path] = []
    seen: set[Path] = set()

    for include in includes:
        candidates = _expand_include(include, root)
        for candidate in candidates:
            resolved = candidate.resolve()
            if resolved in seen:
                continue
            if should_exclude_path(resolved, root=root, exclude_globs=tuple(excludes)):
                continue
            if not looks_like_text_file(resolved):
                continue
            seen.add(resolved)
            files.append(resolved)

    return sorted(files, key=lambda p: p.as_posix())


def _expand_include(include: str, root: Path) -> list[Path]:
    path = Path(include).expanduser()
    if not path.is_absolute():
        path = root / path

    pattern = path.as_posix()
    if any(char in pattern for char in "*?[]"):
        matches = [Path(match) for match in glob(pattern, recursive=True)]
    elif path.exists():
        matches = [path]
    else:
        matches = []

    files: list[Path] = []
    for match in matches:
        if match.is_file():
            files.append(match)
        elif match.is_dir():
            files.extend(p for p in match.rglob("*") if p.is_file())
    return files


def ingest_file(
    path: Path,
    workspace: Path | None = None,
    source_type: str = "file",
    max_bytes: int = 512 * 1024,
) -> IngestedRecord | None:
    stat = path.stat()
    if stat.st_size > max_bytes:
        return None

    raw = path.read_bytes()
    if b"\x00" in raw:
        return None

    try:
        content = raw.decode("utf-8")
    except UnicodeDecodeError:
        content = raw.decode("utf-8", errors="replace")

    content, redactions = redact_secrets(content)
    content_hash = hashlib.sha256(content.encode("utf-8")).hexdigest()
    resolved = path.expanduser().resolve()
    record_id = hashlib.sha256(resolved.as_posix().encode("utf-8")).hexdigest()
    root = (workspace or Path.cwd()).expanduser().resolve()
    title = title_for_path(resolved)
    metadata = {
        "bytes": stat.st_size,
        "mtime": datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc).isoformat(),
        "extension": resolved.suffix.lower(),
        "redactions": redactions,
    }

    return IngestedRecord(
        id=record_id,
        source_type=source_type,
        source_path=resolved.as_posix(),
        workspace=root.as_posix(),
        title=title,
        content=content,
        content_hash=content_hash,
        metadata_json=json.dumps(metadata, sort_keys=True),
        updated_at=datetime.now(timezone.utc).isoformat(),
    )


def looks_like_text_file(path: Path) -> bool:
    if path.suffix.lower() in TEXT_EXTENSIONS:
        return True
    try:
        chunk = path.read_bytes()[:2048]
    except OSError:
        return False
    if b"\x00" in chunk:
        return False
    if not chunk:
        return True
    printable = sum(1 for byte in chunk if byte in b"\n\r\t" or 32 <= byte <= 126)
    return printable / len(chunk) > 0.85


def title_for_path(path: Path) -> str:
    if path.name.lower() in {"readme.md", "index.md"} and path.parent.name:
        return path.parent.name
    return path.name
