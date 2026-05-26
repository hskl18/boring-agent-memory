from __future__ import annotations

import json
import tempfile
from pathlib import Path

from boring_agent_memory.canonical import verify_canonical_source
from boring_agent_memory.index import build_index
from boring_agent_memory.api import memory_query


def main() -> int:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        skills = root / "hermes" / "skills"
        reports = root / "hermes" / "reports" / "sanitized"
        skills.mkdir(parents=True)
        reports.mkdir(parents=True)

        skill = skills / "job-scout.md"
        skill.write_text(
            "# Job Scout\n\n"
            "Workday roles with postingAvailable:false are expired and must not be appended.\n"
            "Always verify the canonical posting state before changing a ledger.\n",
            encoding="utf-8",
        )
        reports.joinpath("daily.md").write_text(
            "Sanitized report: the agent should query memory before asking the user to repeat workflow rules.\n",
            encoding="utf-8",
        )

        db_path = root / ".bam" / "hermes-memory.db"
        stats = build_index(
            db_path,
            includes=[str(skills), str(reports)],
            excludes=["**/.env", "**/secrets/**"],
            workspace=root,
            source_type="hermes_file",
        )
        results = memory_query(
            "Workday postingAvailable false",
            limit=3,
            source_type="hermes_file",
            db_path=db_path,
        )
        verification = verify_canonical_source(db_path, skill)

        print(
            json.dumps(
                {
                    "database": db_path.as_posix(),
                    "build": stats,
                    "query_results": [result.to_dict() for result in results],
                    "canonical_verification": verification,
                },
                indent=2,
                ensure_ascii=False,
            )
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
