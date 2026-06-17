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

Returns a list of `QueryResult` objects:

```python
for result in results:
    print(result.source_path)
    print(result.title)
    print(result.score)
    print(result.snippet)
```

Convert to dictionaries:

```python
payload = [result.to_dict() for result in results]
```

## Agent Rule

`memory_query()` returns recall hints, not authority. Agents should read the cited source path before making current-state claims or state-changing edits.

## Lower-Level APIs

The package also exposes internal modules for building and inspecting indexes:

```python
from boring_agent_memory.index import build_index
from boring_agent_memory.canonical import verify_canonical_source
```

These are stable enough for local use, but `memory_query()` is the intended agent-facing surface.
