# Configuration

`bam build --config memory.yaml` accepts YAML, TOML, or JSON.

## Example

```yaml
index_path: ~/.bam/agent-memory.db
workspace: ~/project
source_type: canonical_file

include:
  - ~/agent/skills
  - ~/agent/bug-log.md
  - ~/project/*/docs

exclude:
  - "**/.env"
  - "**/secrets/**"
  - "**/auth.json"
  - "**/*.sqlite"

privacy:
  redact_secrets: true
  max_file_size_kb: 512
```

## Fields

`index_path`
: SQLite database path. Defaults to `.bam/memory.db`.

`database`
: Backward-compatible alias for `index_path`.

`workspace`
: Root used for resolving relative include paths.

`source_type`
: Label stored on indexed records. Use this to separate sources such as `skill_file`, `project_doc`, or `canonical_file`.

`include`
: List of files, directories, or glob patterns to index. Directories are scanned recursively.

`exclude`
: Glob patterns to skip. These are added to the default privacy excludes.

`privacy.max_file_size_kb`
: Maximum candidate file size in KiB. Defaults to `512`.

`max_bytes`
: Backward-compatible top-level alias for maximum file size.

## Path Resolution

Relative `index_path` and `workspace` values are resolved relative to the config file location. Relative `include` values are resolved relative to `workspace`, or the current directory when no workspace is set. Include entries may use glob patterns such as `~/project/*/docs` or `docs/**/*.md`.

## Privacy Defaults

The indexer always skips common secret-bearing paths such as `.env`, key files, `.git`, dependency folders, virtualenvs, caches, and `secrets` folders. See [privacy-model.md](privacy-model.md).
