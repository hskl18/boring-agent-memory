from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class CliTests(unittest.TestCase):
    def test_cli_build_query_and_stdio_server(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "docs").mkdir()
            (root / "docs" / "canonical.md").write_text(
                "Canonical files are truth. BM25 recall is context.\n",
                encoding="utf-8",
            )
            db_path = root / ".bam" / "memory.db"
            env = {**os.environ, "PYTHONPATH": str(ROOT / "src")}

            build = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "boring_agent_memory.cli",
                    "--db",
                    str(db_path),
                    "build",
                    "--include",
                    "docs",
                    "--workspace",
                    str(root),
                    "--json",
                ],
                cwd=root,
                env=env,
                text=True,
                capture_output=True,
                check=True,
            )
            self.assertEqual(json.loads(build.stdout)["indexed"], 1)

            query = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "boring_agent_memory.cli",
                    "--db",
                    str(db_path),
                    "query",
                    "BM25 recall",
                    "--json",
                ],
                cwd=root,
                env=env,
                text=True,
                capture_output=True,
                check=True,
            )
            self.assertEqual(json.loads(query.stdout)["results"][0]["title"], "canonical.md")

            served = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "boring_agent_memory.cli",
                    "--db",
                    str(db_path),
                    "serve",
                    "--stdio",
                ],
                cwd=root,
                env=env,
                input='{"query":"canonical truth","limit":1}\n',
                text=True,
                capture_output=True,
                check=True,
            )
            response = json.loads(served.stdout)
            self.assertTrue(response["ok"])
            self.assertEqual(response["results"][0]["title"], "canonical.md")


if __name__ == "__main__":
    unittest.main()

