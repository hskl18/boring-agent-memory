# Claude Code Usage

Keep Claude's long-term memory small and use Boring Agent Memory as a local recall layer over trusted files.

Example:

```bash
bam build --include ~/.claude/CLAUDE.md --include docs/ --exclude '**/.env'
bam query "statusline used percent effort display" --limit 3
```

