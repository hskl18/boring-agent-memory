from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from boring_agent_memory import index as index_module
from boring_agent_memory.index import index_configuration


ROOT = Path(__file__).resolve().parents[1]


class ConfigBuildTests(unittest.TestCase):
    def test_cli_build_uses_yaml_config(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "docs").mkdir()
            (root / "docs" / "memory.md").write_text(
                "Canonical files are durable truth for agent memory.\n",
                encoding="utf-8",
            )
            config = root / "memory.yaml"
            config.write_text(
                """
index_path: .bam/from-config.db
workspace: .
include:
  - docs
exclude:
  - "**/.env"
privacy:
  max_file_size_kb: 128
""".strip(),
                encoding="utf-8",
            )
            env = {**os.environ, "PYTHONPATH": str(ROOT / "src")}

            build = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "boring_agent_memory.cli",
                    "build",
                    "--config",
                    str(config),
                    "--json",
                ],
                cwd=root,
                env=env,
                text=True,
                capture_output=True,
                check=True,
            )

            payload = json.loads(build.stdout)
            self.assertEqual(payload["indexed"], 1)
            self.assertTrue((root / ".bam" / "from-config.db").exists())

    def test_config_accepts_legacy_database_and_max_bytes_fields(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "docs").mkdir()
            (root / "docs" / "memory.md").write_text("Hermes recall layer.\n", encoding="utf-8")
            config = root / "memory.yaml"
            config.write_text(
                """
database: .bam/legacy.db
workspace: .
include:
  - docs
max_bytes: 262144
""".strip(),
                encoding="utf-8",
            )
            env = {**os.environ, "PYTHONPATH": str(ROOT / "src")}

            subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "boring_agent_memory.cli",
                    "build",
                    "--config",
                    str(config),
                    "--json",
                ],
                cwd=root,
                env=env,
                text=True,
                capture_output=True,
                check=True,
            )

            self.assertTrue((root / ".bam" / "legacy.db").exists())

    def test_configuration_fingerprint_is_order_stable_and_chunk_sensitive(self) -> None:
        workspace = ROOT.resolve()
        _, first = index_configuration(
            ["docs", "README.md"], ["**/*.tmp", "**/.env"], workspace, "file", 1024, 1600
        )
        _, reordered = index_configuration(
            ["README.md", "docs"], ["**/.env", "**/*.tmp"], workspace, "file", 1024, 1600
        )
        _, changed = index_configuration(
            ["README.md", "docs"], ["**/.env", "**/*.tmp"], workspace, "file", 1024, 800
        )

        self.assertEqual(first, reordered)
        self.assertNotEqual(first, changed)

        original_patterns = index_module.SECRET_PATTERNS
        changed_patterns = (
            re.compile(original_patterns[0].pattern, original_patterns[0].flags | re.IGNORECASE),
            *original_patterns[1:],
        )
        with patch.object(index_module, "SECRET_PATTERNS", changed_patterns):
            _, privacy_changed = index_configuration(
                ["docs", "README.md"],
                ["**/*.tmp", "**/.env"],
                workspace,
                "file",
                1024,
                1600,
            )
        self.assertNotEqual(first, privacy_changed)


if __name__ == "__main__":
    unittest.main()
