# Python API

The public Python API is intentionally small.

## memory_query

```python
from boring_agent_memory import memory_query

results = memory_query(
    "canonical source rule",
    limit=5,
    source_type="canonical_file",
    db_path="~/.bam/agent-memory.db",
    workspace="~/project/app",
)
```

Pass `strict=True` to drop the any-term fallback, so every result matches every term the query tokenizer keeps (Latin letters, digits, and CJK; other scripts are dropped) in its indexed fields (text, heading, title, and path) and a question no file answers is more likely to return nothing.
Strict results still need the same source check as any other result.

`db_path` expands `~`.
A missing database raises `FileNotFoundError` instead of creating an empty index.

Returns a list of `QueryResult` objects:

```python
for result in results:
    print(result.citation)
    print(result.chunk_id)
    print(result.heading)
    print(result.start_line, result.end_line)
    print(result.title)
    print(result.score)
    print(result.snippet)
```

Convert to dictionaries:

```python
payload = [result.to_dict() for result in results]
```

## Agent Rule

`memory_query()` returns recall hints, not authority.
Agents should read the cited source path and line span before making current-state claims or state-changing edits.

## Lower-Level APIs

The package also exposes internal modules for building and inspecting indexes:

```python
from boring_agent_memory.index import build_index, update_index
from boring_agent_memory.canonical import verify_canonical_source
```

`build_index()` and `update_index()` are stable enough for local integration, but `memory_query()` remains the intended agent-facing surface.
`verify_canonical_source()` returns `verification_available: false` and `content_hash_match: null` for migrated legacy rows whose raw-byte baseline is unknowable until a full rebuild.
