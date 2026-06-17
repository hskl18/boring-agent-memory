from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import TextIO

from .query import query_memory


def serve_stdio(
    db_path: Path | str,
    stdin: TextIO = sys.stdin,
    stdout: TextIO = sys.stdout,
) -> int:
    for line in stdin:
        line = line.strip()
        if not line:
            continue
        try:
            request = json.loads(line)
            query = str(request["query"])
            limit = int(request.get("limit", 5))
            source_type = request.get("source_type")
            workspace = request.get("workspace")
            results = [
                result.to_dict()
                for result in query_memory(
                    db_path,
                    query,
                    limit=limit,
                    source_type=source_type,
                    workspace=workspace,
                )
            ]
            response = {"ok": True, "query": query, "results": results}
        except Exception as exc:  # noqa: BLE001 - stdio server must report errors as data.
            response = {"ok": False, "error": str(exc)}
        stdout.write(json.dumps(response, ensure_ascii=False) + "\n")
        stdout.flush()
    return 0
