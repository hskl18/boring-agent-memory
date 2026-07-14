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
                input=f'{{"query":"canonical truth","limit":1,"workspace":"{root}"}}\n',
                text=True,
                capture_output=True,
                check=True,
            )
            response = json.loads(served.stdout)
            self.assertTrue(response["ok"])
            self.assertEqual(response["results"][0]["title"], "canonical.md")

    def test_cli_update_dry_run_and_apply(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "docs").mkdir()
            source = root / "docs" / "canonical.md"
            source.write_text("Original CLI update value.\n", encoding="utf-8")
            db_path = root / ".bam" / "memory.db"
            env = {**os.environ, "PYTHONPATH": str(ROOT / "src")}
            base = [
                sys.executable,
                "-m",
                "boring_agent_memory.cli",
                "--db",
                str(db_path),
            ]
            source_args = ["--include", "docs", "--workspace", str(root), "--json"]
            subprocess.run(
                [*base, "build", *source_args],
                cwd=root,
                env=env,
                check=True,
                capture_output=True,
                text=True,
            )
            source.write_text("Replacement CLI update value.\n", encoding="utf-8")

            dry_run = subprocess.run(
                [*base, "update", *source_args, "--dry-run"],
                cwd=root,
                env=env,
                check=True,
                capture_output=True,
                text=True,
            )
            self.assertEqual(json.loads(dry_run.stdout)["modified"], 1)

            applied = subprocess.run(
                [*base, "update", *source_args],
                cwd=root,
                env=env,
                check=True,
                capture_output=True,
                text=True,
            )
            self.assertTrue(json.loads(applied.stdout)["applied"])

            query = subprocess.run(
                [*base, "query", "Replacement CLI", "--json"],
                cwd=root,
                env=env,
                check=True,
                capture_output=True,
                text=True,
            )
            payload = json.loads(query.stdout)
            self.assertIn("citation", payload["results"][0])
            self.assertIn("chunk_id", payload["results"][0])


if __name__ == "__main__":
    unittest.main()
