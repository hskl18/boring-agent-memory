# Configuration

`bam build --config memory.yaml` and `bam update --config memory.yaml` accept YAML, TOML, or JSON.

## Example

```yaml
index_path: ~/.bam/agent-memory.db
workspace: ~/project
source_type: canonical_file
chunk_size: 1600

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
: SQLite database path.
The default is `.bam/memory.db`.

`database`
: Compatibility alias for `index_path`.

`workspace`
: Root used for resolving relative include paths and recording source identity.

`source_type`
: Label stored on indexed documents.

`include`
: Files, directories, or glob patterns to index.
Directories are scanned recursively.

`exclude`
: Additional glob patterns to skip after the built-in privacy exclusions.

`chunk_size`
: Preferred maximum chunk size in characters.
The default is `1600`.
Protected Markdown blocks can exceed the bound rather than being split incorrectly.
A value of `0` disables chunking and is intended for controlled benchmark comparisons.

`privacy.max_file_size_kb`
: Maximum candidate file size in KiB.
The default is `512`.

`max_bytes`
: Compatibility top-level field for the maximum file size.

## Path Resolution

Relative `index_path` and `workspace` values are resolved relative to the config file.
Relative include values are resolved against `workspace`, or the current directory when no workspace is set.
Include entries may use glob patterns such as `~/project/*/docs` or `docs/**/*.md`.

## Incremental Configuration Contract

Every build records a canonical configuration fingerprint.
The fingerprint covers normalized include and exclude patterns, workspace, source type, maximum bytes, chunk size, schema and chunker versions, tokenizer, identifier version, and the privacy-policy digest.
Ordering include or exclude entries does not change the fingerprint.
Changing an indexing rule requires a new `bam build` before `bam update` can resume.

## Privacy Defaults

The indexer always skips common secret-bearing paths such as `.env`, key files, `.git`, dependency folders, virtual environments, caches, and `secrets` folders.
See [privacy-model.md](privacy-model.md).
