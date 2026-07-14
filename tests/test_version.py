from __future__ import annotations

import importlib.metadata
import os
import subprocess
import sys
import unittest
from pathlib import Path

from boring_agent_memory import __version__

try:
    import tomllib
except ModuleNotFoundError:  # pragma: no cover
    import tomli as tomllib


ROOT = Path(__file__).resolve().parents[1]


class VersionTests(unittest.TestCase):
    def test_runtime_and_cli_derive_version_from_package_metadata(self) -> None:
        metadata_version = importlib.metadata.version("boring-agent-memory")
        pyproject = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
        self.assertEqual(pyproject["project"]["version"], "0.2.0")
        self.assertEqual(metadata_version, "0.2.0")
        self.assertEqual(__version__, metadata_version)

        result = subprocess.run(
            [sys.executable, "-m", "boring_agent_memory.cli", "--version"],
            cwd=ROOT,
            env={**os.environ, "PYTHONPATH": str(ROOT / "src")},
            text=True,
            capture_output=True,
            check=True,
        )
        self.assertEqual(result.stdout.strip(), "bam 0.2.0")


if __name__ == "__main__":
    unittest.main()
