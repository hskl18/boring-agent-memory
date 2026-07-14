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

    def test_front_insertion_never_rebinds_an_existing_chunk_id(self) -> None:
        before = chunk_text(
            "document-id",
            """# Policy

Alpha rule with durable meaning.

Beta rule with durable meaning.

Gamma rule with durable meaning.
""",
            ".md",
            max_chars=40,
        )
        after = chunk_text(
            "document-id",
            """# Policy

Inserted rule with new meaning.

Alpha rule with durable meaning.

Beta rule with durable meaning.

Gamma rule with durable meaning.
""",
            ".md",
            max_chars=40,
        )

        before_by_id = {chunk.id: chunk.content for chunk in before}
        after_by_id = {chunk.id: chunk.content for chunk in after}
        reused_ids = before_by_id.keys() & after_by_id.keys()

        self.assertGreaterEqual(len(reused_ids), 4)
        self.assertEqual(
            {chunk_id: before_by_id[chunk_id] for chunk_id in reused_ids},
            {chunk_id: after_by_id[chunk_id] for chunk_id in reused_ids},
        )

    def test_semantic_content_change_gets_a_new_chunk_id(self) -> None:
        before = chunk_text("document-id", "# Policy\n\nOld rule.\n", ".md", max_chars=100)
        after = chunk_text("document-id", "# Policy\n\nNew rule.\n", ".md", max_chars=100)

        self.assertNotEqual(before[0].id, after[0].id)
        self.assertNotEqual(before[0].content_hash, after[0].content_hash)

    def test_deletion_preserves_ids_for_surviving_content(self) -> None:
        before = chunk_text(
            "document-id",
            "# Policy\n\nAlpha durable rule.\n\nBeta removable rule.\n\nGamma durable rule.\n",
            ".md",
            max_chars=25,
        )
        after = chunk_text(
            "document-id",
            "# Policy\n\nAlpha durable rule.\n\nGamma durable rule.\n",
            ".md",
            max_chars=25,
        )

        before_ids = {chunk.content: chunk.id for chunk in before}
        after_ids = {chunk.content: chunk.id for chunk in after}

        self.assertNotIn("Beta removable rule.", after_ids)
        self.assertEqual(before_ids["Alpha durable rule."], after_ids["Alpha durable rule."])
        self.assertEqual(before_ids["Gamma durable rule."], after_ids["Gamma durable rule."])

    def test_split_and_merge_never_rebind_a_chunk_id(self) -> None:
        content = """# Policy

Alpha rule with durable meaning.

Beta rule with durable meaning.
"""
        merged = chunk_text("document-id", content, ".md", max_chars=200)
        split = chunk_text("document-id", content, ".md", max_chars=40)

        merged_by_id = {chunk.id: chunk.content for chunk in merged}
        split_by_id = {chunk.id: chunk.content for chunk in split}
        reused_ids = merged_by_id.keys() & split_by_id.keys()

        self.assertEqual(len(merged), 1)
        self.assertGreater(len(split), 1)
        self.assertEqual(
            {chunk_id: merged_by_id[chunk_id] for chunk_id in reused_ids},
            {chunk_id: split_by_id[chunk_id] for chunk_id in reused_ids},
        )
        self.assertNotIn(merged[0].id, split_by_id)

    def test_duplicate_heading_insertion_preserves_existing_content_ids(self) -> None:
        before = chunk_text(
            "document-id",
            "# Root\n\n## Retry\n\nAlpha durable body.\n\n## Retry\n\nBeta durable body.\n",
            ".md",
            max_chars=60,
        )
        after = chunk_text(
            "document-id",
            "# Root\n\n## Retry\n\nInserted body.\n\n## Retry\n\nAlpha durable body.\n\n## Retry\n\nBeta durable body.\n",
            ".md",
            max_chars=60,
        )

        before_alpha = next(chunk for chunk in before if "Alpha durable body." in chunk.content)
        before_beta = next(chunk for chunk in before if "Beta durable body." in chunk.content)
        after_alpha = next(chunk for chunk in after if "Alpha durable body." in chunk.content)
        after_beta = next(chunk for chunk in after if "Beta durable body." in chunk.content)

        self.assertEqual(before_alpha.id, after_alpha.id)
        self.assertEqual(before_beta.id, after_beta.id)

    def test_heading_case_collision_never_rebinds_an_existing_id(self) -> None:
        before = chunk_text(
            "document-id",
            "# Foo\n\nSAMEBODY\n",
            ".md",
            max_chars=8,
        )
        after = chunk_text(
            "document-id",
            "# foo\n\nSAMEBODY\n\n# Foo\n\nSAMEBODY\n",
            ".md",
            max_chars=8,
        )

        before_body = next(chunk for chunk in before if chunk.content == "SAMEBODY")
        after_foo_body = next(
            chunk
            for chunk in after
            if chunk.content == "SAMEBODY" and chunk.heading == "Foo"
        )
        after_lower_body = next(
            chunk
            for chunk in after
            if chunk.content == "SAMEBODY" and chunk.heading == "foo"
        )

        self.assertEqual(before_body.id, after_foo_body.id)
        self.assertNotEqual(before_body.id, after_lower_body.id)

    def test_literal_heading_delimiter_does_not_collide_with_ancestry(self) -> None:
        before = chunk_text(
            "document-id",
            "# A\n\n## B\n\nSAMEBODY\n",
            ".md",
            max_chars=8,
        )
        after = chunk_text(
            "document-id",
            "# A > B\n\nSAMEBODY\n\n# A\n\n## B\n\nSAMEBODY\n",
            ".md",
            max_chars=8,
        )

        before_body = next(chunk for chunk in before if chunk.content == "SAMEBODY")
        after_bodies = [chunk for chunk in after if chunk.content == "SAMEBODY"]

        self.assertEqual(len(after_bodies), 2)
        self.assertNotEqual(before_body.id, after_bodies[0].id)
        self.assertEqual(before_body.id, after_bodies[1].id)

    def test_duplicate_chunks_are_unique_and_fail_closed_across_insertion(self) -> None:
        before = chunk_text(
            "document-id",
            "# Policy\n\nRepeated rule.\n\nRepeated rule.\n",
            ".md",
            max_chars=16,
        )
        after = chunk_text(
            "document-id",
            "# Policy\n\nInserted rule.\n\nRepeated rule.\n\nRepeated rule.\n",
            ".md",
            max_chars=16,
        )

        before_ids = {chunk.id for chunk in before if chunk.content == "Repeated rule."}
        after_ids = {chunk.id for chunk in after if chunk.content == "Repeated rule."}

        self.assertEqual(len(before_ids), 2)
        self.assertEqual(len(after_ids), 2)
        self.assertFalse(before_ids & after_ids)

    def test_duplicate_count_change_invalidates_the_whole_identity_group(self) -> None:
        before = chunk_text(
            "document-id",
            "# H\n\nSAMEBODY\n\n# H\n\nSAMEBODY\n",
            ".md",
            max_chars=8,
        )
        after = chunk_text(
            "document-id",
            "# H\n\nSAMEBODY\n\n# H\n\nSAMEBODY\n\n# H\n\nSAMEBODY\n",
            ".md",
            max_chars=8,
        )

        before_ids = {chunk.id for chunk in before if chunk.content == "SAMEBODY"}
        after_ids = {chunk.id for chunk in after if chunk.content == "SAMEBODY"}

        self.assertEqual(len(before_ids), 2)
        self.assertEqual(len(after_ids), 3)
        self.assertFalse(before_ids & after_ids)

    def test_same_count_duplicate_replacement_invalidates_the_identity_group(self) -> None:
        before = chunk_text(
            "document-id",
            "# H\n\nDUPLICAT\n\nALPHAONE\n\nDUPLICAT\n\nOMEGAONE\n",
            ".md",
            max_chars=8,
        )
        after = chunk_text(
            "document-id",
            "# H\n\nDUPLICAT\n\nDUPLICAT\n\nALPHAONE\n\nOMEGAONE\n",
            ".md",
            max_chars=8,
        )

        before_ids = {chunk.id for chunk in before if chunk.content == "DUPLICAT"}
        after_ids = {chunk.id for chunk in after if chunk.content == "DUPLICAT"}

        self.assertEqual(len(before_ids), 2)
        self.assertEqual(len(after_ids), 2)
        self.assertFalse(before_ids & after_ids)

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
