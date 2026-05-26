from __future__ import annotations

import json
import os
import subprocess
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class DemoTests(unittest.TestCase):
    def test_hermes_demo_runs_end_to_end(self) -> None:
        env = {
            **os.environ,
            "PYTHONPATH": str(ROOT / "src"),
            "PYTHONDONTWRITEBYTECODE": "1",
        }
        run = subprocess.run(
            [sys.executable, "scripts/demo_hermes_layer.py"],
            cwd=ROOT,
            env=env,
            text=True,
            capture_output=True,
            check=True,
        )
        payload = json.loads(run.stdout)
        self.assertEqual(payload["build"]["indexed"], 2)
        self.assertEqual(payload["query_results"][0]["source_type"], "hermes_file")
        self.assertTrue(payload["canonical_verification"]["content_hash_match"])


if __name__ == "__main__":
    unittest.main()
