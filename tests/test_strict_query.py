from __future__ import annotations

import io
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from boring_agent_memory import memory_query
from boring_agent_memory.index import build_index
from boring_agent_memory.server import serve_stdio

ROOT = Path(__file__).resolve().parents[1]


class StrictQueryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name)
        (root / "docs").mkdir()
        (root / "docs" / "deployments.md").write_text("# Deployments\n\nThe cobalt rollback window is fifteen minutes.\n", encoding="utf-8")
        (root / "docs" / "sessions.md").write_text("# Sessions\n\nThe orchid idle timeout is twenty minutes.\n", encoding="utf-8")
        self.db = root / ".bam" / "memory.db"
        build_index(self.db, ["docs"], workspace=root, source_type="doc")

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_default_falls_back_to_an_any_term_match_for_a_cross_wired_question(self) -> None:
        results = memory_query("cobalt idle timeout", db_path=self.db)
        self.assertTrue(results)
        self.assertEqual({result.strategy for result in results}, {"or"})

    def test_strict_returns_nothing_unless_one_chunk_has_every_term(self) -> None:
        self.assertEqual(memory_query("cobalt idle timeout", db_path=self.db, strict=True), [])
        [result] = memory_query("cobalt rollback window", db_path=self.db, strict=True)
        self.assertEqual(result.title, "deployments.md")

    def test_stdio_accepts_strict_and_rejects_a_non_boolean(self) -> None:
        stdin = io.StringIO(
            json.dumps({"query": "cobalt idle timeout", "strict": True}) + "\n"
            + json.dumps({"query": "cobalt idle timeout", "strict": "yes"}) + "\n"
        )
        stdout = io.StringIO()
        serve_stdio(self.db, stdin=stdin, stdout=stdout)
        strict, invalid = [json.loads(line) for line in stdout.getvalue().splitlines()]
        self.assertEqual(strict, {"ok": True, "query": "cobalt idle timeout", "results": []})
        self.assertFalse(invalid["ok"])

    def test_cli_strict_flag(self) -> None:
        command = [sys.executable, "-m", "boring_agent_memory.cli", "--db", str(self.db), "query", "cobalt idle timeout", "--json"]
        env = {"PYTHONPATH": str(ROOT / "src")}
        default = json.loads(subprocess.run(command, capture_output=True, text=True, check=True, env=env).stdout)
        strict = json.loads(subprocess.run([*command, "--strict"], capture_output=True, text=True, check=True, env=env).stdout)
        self.assertTrue(default["results"])
        self.assertEqual(strict["results"], [])


if __name__ == "__main__":
    unittest.main()
