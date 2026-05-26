from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


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


if __name__ == "__main__":
    unittest.main()
