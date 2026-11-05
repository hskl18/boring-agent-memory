"""Regressions for failures that used to look like success: empty results, a replaced index, or misread config."""

from __future__ import annotations

import io
import json
import os
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from boring_agent_memory import index as index_module
from boring_agent_memory import memory_query
from boring_agent_memory.canonical import (
    list_canonical_sources,
    verify_canonical_source,
)
from boring_agent_memory.config import load_config
from boring_agent_memory.embeddings import load_embedding_documents
from boring_agent_memory.index import build_index, update_index
from boring_agent_memory.query import query_memory
from boring_agent_memory.server import serve_stdio

ROOT = Path(__file__).resolve().parents[1]


def run_cli(*args: str, cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "boring_agent_memory.cli", *args],
        cwd=cwd or ROOT,
        env={**os.environ, "PYTHONPATH": str(ROOT / "src")},
        text=True,
        capture_output=True,
        check=False,
    )


def document_count(db_path: Path) -> int:
    return len(list_canonical_sources(db_path))


class TempDirTestCase(unittest.TestCase):
    def setUp(self) -> None:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name).resolve()
        self.db_path = self.root / "memory.db"
        (self.root / "docs").mkdir()
        (self.root / "docs" / "rules.md").write_text(
            "# Rules\n\nThe postingAvailable flag marks expired rows. Roll back within 15 minutes.\n",
            encoding="utf-8",
        )


class FallbackFilterTests(TempDirTestCase):
    def test_like_fallback_honors_filters(self) -> None:
        build_index(self.db_path, ["docs"], workspace=self.root, source_type="runbook")
        # A word fragment cannot match FTS, so only the LIKE fallback can find it.
        fragment = "postingAvail"

        self.assertEqual([r.strategy for r in query_memory(self.db_path, fragment)], ["like"])
        self.assertEqual(len(query_memory(self.db_path, fragment, source_type="runbook")), 1)
        self.assertEqual(query_memory(self.db_path, fragment, source_type="other"), [])
        self.assertEqual(len(query_memory(self.db_path, fragment, workspace=self.root)), 1)
        self.assertEqual(query_memory(self.db_path, fragment, workspace=self.root / "docs"), [])


class CandidateLimitTests(TempDirTestCase):
    def setUp(self) -> None:
        super().setUp()
        sections = "".join(f"# Section {i}\n\nrollback rollback policy zetafragment {i}\n\n" for i in range(40))
        (self.root / "docs" / "long.md").write_text(sections, encoding="utf-8")
        (self.root / "docs" / "short.md").write_text(
            "# Other\n\nrollback zetafragment appears once in a longer sentence about something else.\n",
            encoding="utf-8",
        )
        build_index(self.db_path, ["docs"], workspace=self.root)

    def test_long_document_does_not_hide_another_document_in_fts(self) -> None:
        results = query_memory(self.db_path, "zetafragment", limit=2)
        self.assertEqual({result.title for result in results}, {"long.md", "short.md"})
        self.assertEqual({result.strategy for result in results}, {"phrase"})

    def test_long_document_does_not_hide_another_document_in_like(self) -> None:
        results = query_memory(self.db_path, "tafragment", limit=2)
        self.assertEqual({result.title for result in results}, {"long.md", "short.md"})
        self.assertEqual({result.strategy for result in results}, {"like"})


class ResultLimitTests(TempDirTestCase):
    def test_limit_is_respected_at_the_edges(self) -> None:
        build_index(self.db_path, ["docs"], workspace=self.root)
        self.assertEqual(query_memory(self.db_path, "postingAvailable", limit=0), [])
        self.assertEqual(query_memory(self.db_path, "postingAvailable", limit=-1), [])
        self.assertEqual(len(query_memory(self.db_path, "postingAvailable", limit=1)), 1)


class MissingIndexTests(TempDirTestCase):
    def test_python_api_raises_and_creates_nothing(self) -> None:
        missing = self.root / "typo" / "none.db"
        with self.assertRaisesRegex(FileNotFoundError, "bam build"):
            memory_query("rollback", db_path=missing)
        self.assertFalse(missing.parent.exists())

    def test_canonical_helpers_raise_and_create_nothing(self) -> None:
        missing = self.root / "typo" / "none.db"
        with self.assertRaisesRegex(FileNotFoundError, "bam build"):
            verify_canonical_source(missing, self.root / "docs" / "rules.md")
        with self.assertRaisesRegex(FileNotFoundError, "bam build"):
            list_canonical_sources(missing)
        self.assertFalse(missing.parent.exists())

    def test_cli_query_and_inspect_fail_and_create_nothing(self) -> None:
        missing = self.root / "typo" / "none.db"
        for args in (["query", "rollback"], ["inspect"], ["inspect", "docs/rules.md"]):
            result = run_cli("--db", str(missing), *args)
            self.assertEqual(result.returncode, 2, args)
            self.assertIn("bam build", result.stderr)
            self.assertNotIn("Traceback", result.stderr)
        self.assertFalse(missing.parent.exists())

    def test_embedding_loader_raises_and_creates_nothing(self) -> None:
        missing = self.root / "typo" / "none.db"
        with self.assertRaisesRegex(FileNotFoundError, "bam build"):
            load_embedding_documents(missing)
        self.assertFalse(missing.parent.exists())

    def test_stdio_reports_missing_index_as_data(self) -> None:
        stdout = io.StringIO()
        serve_stdio(self.root / "none.db", stdin=io.StringIO('{"query": "rollback"}\n'), stdout=stdout)
        response = json.loads(stdout.getvalue())
        self.assertFalse(response["ok"])
        self.assertIn("bam build", response["error"])

    def test_health_reports_missing_index_without_creating_it(self) -> None:
        missing = self.root / "typo" / "none.db"
        result = run_cli("--db", str(missing), "health", "--json")
        self.assertEqual(result.returncode, 0)
        self.assertFalse(json.loads(result.stdout)["ok"])
        self.assertFalse(missing.parent.exists())


class TildePathTests(TempDirTestCase):
    def test_tilde_database_path_expands_for_build_update_and_query(self) -> None:
        workdir = self.root / "elsewhere"
        workdir.mkdir()
        self.addCleanup(os.chdir, os.getcwd())
        os.chdir(workdir)
        includes = [str(self.root / "docs")]

        with mock.patch.dict(os.environ, {"HOME": str(self.root)}):
            build_index("~/m.db", includes, workspace=self.root)
            update_index("~/m.db", includes, workspace=self.root, dry_run=True)
            results = memory_query("postingAvailable", db_path="~/m.db")

        self.assertEqual(len(results), 1)
        self.assertTrue((self.root / "m.db").exists())
        self.assertEqual(list(workdir.iterdir()), [])

    def test_cli_expands_a_quoted_tilde_database_path(self) -> None:
        env_home = {"HOME": str(self.root)}
        with mock.patch.dict(os.environ, env_home):
            build = run_cli("--db", "~/m.db", "build", "--include", str(self.root / "docs"), cwd=self.root)
            query = run_cli("--db", "~/m.db", "query", "postingAvailable", "--json", cwd=self.root)
            status = run_cli("--db", "~/m.db", "status", "--json", cwd=self.root)
        self.assertEqual(build.returncode, 0, build.stderr)
        self.assertEqual(len(json.loads(query.stdout)["results"]), 1)
        self.assertTrue(json.loads(status.stdout)["database_exists"])
        self.assertFalse((self.root / "~").exists())


class IndexSafetyTests(TempDirTestCase):
    def setUp(self) -> None:
        super().setUp()
        build_index(self.db_path, ["docs"], workspace=self.root)

    def test_missing_include_path_fails_and_keeps_the_index(self) -> None:
        with self.assertRaisesRegex(OSError, "docs-typo"):
            build_index(self.db_path, ["docs-typo"], workspace=self.root)
        self.assertEqual(document_count(self.db_path), 1)

    def test_missing_include_path_fails_update_and_keeps_the_index(self) -> None:
        with self.assertRaisesRegex(OSError, "docs-typo"):
            update_index(self.db_path, ["docs-typo"], workspace=self.root)
        self.assertEqual(document_count(self.db_path), 1)

    def test_cli_reports_missing_include_path(self) -> None:
        result = run_cli("--db", str(self.db_path), "build", "--include", "docs-typo", "--workspace", str(self.root))
        self.assertEqual(result.returncode, 2)
        self.assertIn("docs-typo", result.stderr)
        self.assertEqual(document_count(self.db_path), 1)

    def test_glob_matching_nothing_does_not_replace_a_populated_index(self) -> None:
        with self.assertRaisesRegex(ValueError, "populated index"):
            build_index(self.db_path, ["nothing/*/docs"], workspace=self.root)
        self.assertEqual(document_count(self.db_path), 1)

    def test_empty_check_holds_the_write_lock_on_a_new_index(self) -> None:
        checks: list[bool] = []
        real_connect = index_module.connect

        def traced_connect(path: object) -> sqlite3.Connection:
            conn = real_connect(path)

            def record(sql: str) -> None:
                if sql.startswith("SELECT 1 FROM documents"):
                    checks.append(conn.in_transaction)

            conn.set_trace_callback(record)
            return conn

        with mock.patch.object(index_module, "connect", traced_connect):
            build_index(self.root / "new.db", ["nothing/*/docs"], workspace=self.root)

        self.assertEqual(checks, [True])

    def test_first_build_may_be_empty(self) -> None:
        (self.root / "empty").mkdir()
        fresh = self.root / "fresh.db"
        self.assertEqual(build_index(fresh, ["empty"], workspace=self.root)["indexed"], 0)
        self.assertEqual(document_count(fresh), 0)


class EvalTests(TempDirTestCase):
    def test_eval_leaves_the_named_database_alone(self) -> None:
        build_index(self.db_path, ["docs"], workspace=self.root)
        result = run_cli("--db", str(self.db_path), "eval", "--json")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(
            [source["title"] for source in list_canonical_sources(self.db_path)],
            ["rules.md"],
        )

    def test_eval_without_fixtures_explains_itself(self) -> None:
        result = run_cli("eval", "--json", cwd=self.root)
        self.assertEqual(result.returncode, 2)
        self.assertIn("--fixtures", result.stderr)
        self.assertNotIn("Traceback", result.stderr)


class SimpleYamlTests(TempDirTestCase):
    def load(self, text: str) -> object:
        path = self.root / "memory.yaml"
        path.write_text(text, encoding="utf-8")
        return load_config(path)

    def test_flow_list_is_rejected_instead_of_read_as_a_literal_path(self) -> None:
        with self.assertRaisesRegex(ValueError, "block list"):
            self.load('include: ["docs"]\n')

    def test_hash_inside_quotes_or_a_word_is_not_a_comment(self) -> None:
        config = self.load('include:\n  - "a#b"\n  - c#d\n  - e  # a comment\n')
        self.assertEqual(config.include, ("a#b", "c#d", "e"))

    def test_quoted_hash_after_an_apostrophe_word_is_not_lost(self) -> None:
        config = self.load("source_type: don't  # a comment\n")
        self.assertEqual(config.source_type, "don't")

    def test_unindented_list_item_with_a_colon_stays_a_list_item(self) -> None:
        config = self.load("include:\n- a:b\n")
        self.assertEqual(config.include, ("a:b",))

    def test_unsupported_line_is_rejected_instead_of_dropped(self) -> None:
        with self.assertRaisesRegex(ValueError, "line 2"):
            self.load("source_type: file\n  - stray\n")

    def test_keys_mixed_with_list_items_are_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "mixes keys and list items"):
            self.load("include:\n  - docs\nprivacy:\n  max_file_size_kb: 1\n  - stray\n")

    def test_escaped_quotes_are_rejected_instead_of_truncated(self) -> None:
        for value in ('"a\\" # b.md"', "'it''s # notes.md'", '"unterminated'):
            with self.assertRaisesRegex(ValueError, "quoting"):
                self.load(f"include:\n  - {value}\n")

    def test_shipped_examples_still_parse(self) -> None:
        examples = sorted((ROOT / "examples").glob("*.yaml"))
        self.assertTrue(examples)
        for example in examples:
            self.assertTrue(load_config(example).include, example)


if __name__ == "__main__":
    unittest.main()
