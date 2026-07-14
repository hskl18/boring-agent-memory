from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from boring_agent_memory.chunking import chunk_text
from boring_agent_memory.index import build_index
from boring_agent_memory.query import query_memory


class ChunkingTests(unittest.TestCase):
    def test_markdown_chunks_preserve_headings_lines_and_structured_blocks(self) -> None:
        content = """# 操作规则

Use the ClerkInvitationError recovery path.

## Retry

```python
def retry_invite():
    return \"/portal/accept-token\"
```

## Retry

| code | action |
| --- | --- |
| HTTP_409 | refresh |
"""
        chunks = chunk_text("document-id", content, ".md", max_chars=100)

        self.assertGreaterEqual(len(chunks), 3)
        self.assertEqual(len({chunk.id for chunk in chunks}), len(chunks))
        self.assertTrue(any("操作规则 > Retry" == chunk.heading for chunk in chunks))
        code_chunk = next(chunk for chunk in chunks if "def retry_invite" in chunk.content)
        self.assertIn("```python", code_chunk.content)
        self.assertIn("```", code_chunk.content.splitlines()[-1])
        table_chunk = next(chunk for chunk in chunks if "HTTP_409" in chunk.content)
        self.assertIn("| --- | --- |", table_chunk.content)
        self.assertGreaterEqual(code_chunk.start_line, 1)
        self.assertGreaterEqual(code_chunk.end_line, code_chunk.start_line)

    def test_chunk_ids_are_stable_when_body_text_changes(self) -> None:
        before = chunk_text("document-id", "# Policy\n\nOld rule.\n", ".md", max_chars=100)
        after = chunk_text("document-id", "# Policy\n\nNew rule.\n", ".md", max_chars=100)

        self.assertEqual([chunk.id for chunk in before], [chunk.id for chunk in after])
        self.assertNotEqual(before[0].content_hash, after[0].content_hash)

    def test_query_result_has_heading_aware_line_citation(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "docs").mkdir()
            (root / "docs" / "runbook.md").write_text(
                "# Deploy\n\nIntro.\n\n## Rollback\n\nUse rollback token ALPHA_409.\n",
                encoding="utf-8",
            )
            db_path = root / ".bam" / "memory.db"
            build_index(db_path, ["docs"], workspace=root, chunk_size=80)

            result = query_memory(db_path, "ALPHA_409", limit=1)[0]

            self.assertEqual(result.heading, "Deploy > Rollback")
            self.assertIn("runbook.md#Deploy > Rollback:L", result.citation)
            self.assertGreaterEqual(result.end_line, result.start_line)


if __name__ == "__main__":
    unittest.main()
