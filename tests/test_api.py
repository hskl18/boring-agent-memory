from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from boring_agent_memory import memory_query
from boring_agent_memory.index import build_index


class ApiTests(unittest.TestCase):
    def test_memory_query_is_the_agent_facing_api(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "skills").mkdir()
            (root / "skills" / "workday.md").write_text(
                "Workday postingAvailable false means the job is expired.\n",
                encoding="utf-8",
            )
            db_path = root / ".bam" / "memory.db"
            build_index(db_path, ["skills"], workspace=root, source_type="skill_file")

            results = memory_query(
                "postingAvailable false",
                limit=1,
                source_type="skill_file",
                db_path=db_path,
            )

            self.assertEqual(len(results), 1)
            self.assertEqual(results[0].title, "workday.md")


if __name__ == "__main__":
    unittest.main()
