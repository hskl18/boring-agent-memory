from __future__ import annotations

import json
import shutil
import tempfile
from pathlib import Path

from boring_agent_memory.index import build_index, update_index
from boring_agent_memory.query import query_memory


ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    with tempfile.TemporaryDirectory() as tmp:
        workspace = Path(tmp) / "corpus"
        shutil.copytree(ROOT / "benchmarks" / "v2" / "corpus", workspace)
        db_path = Path(tmp) / "memory.db"
        build = build_index(db_path, ["."], workspace=workspace)

        deployments = workspace / "canonical" / "deployments.md"
        deployments.write_text(
            deployments.read_text(encoding="utf-8").replace(
                "# Current deployment policy",
                "# Current deployment and rollback policy",
            ),
            encoding="utf-8",
        )
        (workspace / "canonical" / "invitations.md").rename(
            workspace / "canonical" / "invite-policy.md"
        )
        (workspace / "lifecycle" / "removed-source.md").unlink()

        dry_run = update_index(db_path, ["."], workspace=workspace, dry_run=True)
        applied = update_index(db_path, ["."], workspace=workspace)
        removed_results = query_memory(db_path, "obsolete-lantern-rule")
        renamed_results = query_memory(db_path, "ClerkInvitationError", limit=1)
        payload = {
            "build": build,
            "dry_run": dry_run,
            "applied": applied,
            "verification": {
                "removed_source_absent": not removed_results,
                "renamed_source": (
                    Path(renamed_results[0].source_path).name if renamed_results else None
                ),
            },
        }
        print(json.dumps(payload, indent=2, sort_keys=True))
        expected = {
            "added": 0,
            "modified": 1,
            "moved": 1,
            "removed": 1,
        }
        actual = {key: dry_run[key] for key in expected}
        return 0 if actual == expected and payload["verification"] == {
            "removed_source_absent": True,
            "renamed_source": "invite-policy.md",
        } else 1


if __name__ == "__main__":
    raise SystemExit(main())
