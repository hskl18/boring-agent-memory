from __future__ import annotations

import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .chunking import DEFAULT_CHUNK_SIZE
from .schema import DEFAULT_DB_PATH

if sys.version_info >= (3, 11):
    import tomllib as toml_loader
else:  # pragma: no cover - exercised on Python 3.10.
    import tomli as toml_loader


@dataclass(frozen=True)
class MemoryConfig:
    index_path: Path = DEFAULT_DB_PATH
    include: tuple[str, ...] = ()
    exclude: tuple[str, ...] = ()
    workspace: Path | None = None
    source_type: str = "file"
    max_file_size_kb: int = 512
    chunk_size: int = DEFAULT_CHUNK_SIZE

    @property
    def max_bytes(self) -> int:
        return self.max_file_size_kb * 1024


def load_config(path: Path | str) -> MemoryConfig:
    config_path = Path(path).expanduser()
    raw = _load_mapping(config_path)
    base_dir = config_path.resolve().parent
    privacy_value = raw.get("privacy")
    privacy: dict[str, Any] = privacy_value if isinstance(privacy_value, dict) else {}

    index_path = _path_value(raw.get("index_path", raw.get("database")), DEFAULT_DB_PATH, base_dir)
    workspace = _optional_path_value(raw.get("workspace"), base_dir)
    if "max_bytes" in raw:
        max_file_size_kb = max(1, int(raw["max_bytes"]) // 1024)
    else:
        max_file_size_kb = int(privacy.get("max_file_size_kb", raw.get("max_file_size_kb", 512)))

    return MemoryConfig(
        index_path=index_path,
        include=tuple(_list_value(raw.get("include"))),
        exclude=tuple(_list_value(raw.get("exclude"))),
        workspace=workspace,
        source_type=str(raw.get("source_type", "file")),
        max_file_size_kb=max_file_size_kb,
        chunk_size=int(raw.get("chunk_size", DEFAULT_CHUNK_SIZE)),
    )


def _load_mapping(path: Path) -> dict[str, Any]:
    text = path.read_text(encoding="utf-8")
    suffix = path.suffix.lower()
    if suffix == ".json":
        data = json.loads(text)
    elif suffix == ".toml":
        data = toml_loader.loads(text)
    elif suffix in {".yaml", ".yml"}:
        data = _parse_simple_yaml(text)
    else:
        raise ValueError(f"Unsupported config format: {path.suffix}")
    if not isinstance(data, dict):
        raise ValueError("Config root must be a mapping")
    return data


def _parse_simple_yaml(text: str) -> dict[str, Any]:
    """Parse the small YAML subset used by BAM examples without a dependency."""
    data: dict[str, Any] = {}
    current_key: str | None = None

    for raw_line in text.splitlines():
        line = raw_line.split("#", 1)[0].rstrip()
        if not line.strip():
            continue

        stripped = line.strip()
        if not line.startswith(" ") and ":" in stripped:
            key, value = stripped.split(":", 1)
            key = key.strip()
            value = value.strip()
            if value:
                data[key] = _scalar(value)
                current_key = None
            else:
                data[key] = {}
                current_key = key
            continue

        if stripped.startswith("- ") and current_key:
            if not isinstance(data[current_key], list):
                data[current_key] = []
            data[current_key].append(_scalar(stripped[2:].strip()))
            continue

        if current_key and isinstance(data.get(current_key), dict) and ":" in stripped:
            key, value = stripped.split(":", 1)
            data[current_key][key.strip()] = _scalar(value.strip())

    return data


def _scalar(value: str) -> Any:
    value = value.strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
        return value[1:-1]
    if value.lower() in {"true", "false"}:
        return value.lower() == "true"
    try:
        return int(value)
    except ValueError:
        return value


def _path_value(value: Any, default: Path, base_dir: Path) -> Path:
    if value is None:
        return default
    path = Path(str(value)).expanduser()
    return path if path.is_absolute() else base_dir / path


def _optional_path_value(value: Any, base_dir: Path) -> Path | None:
    if value in {None, ""}:
        return None
    path = Path(str(value)).expanduser()
    return path if path.is_absolute() else base_dir / path


def _list_value(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [value]
    if isinstance(value, list):
        return [str(item) for item in value]
    raise ValueError("Expected a string or list")
