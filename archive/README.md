# D-GRID Archives

This directory contains archived task results from the D-GRID system.

## Structure

Archives are organized by month:
```
archive/
├── YYYY-MM.tar.gz       # Compressed monthly archives
└── MANIFEST.md          # Archive manifest with metadata
```

## Accessing Archives

To extract an archive:
```bash
tar -xzf YYYY-MM.tar.gz
```

## Retention Policy

- Results older than 30 days are automatically archived
- Archives are compressed to save space
- Archives are kept indefinitely for audit purposes

## Manual Archival

To manually trigger archival:
1. Go to GitHub Actions
2. Select "Archive Old Results" workflow
3. Click "Run workflow"
4. Optionally specify custom retention (default: 30 days)

## Archive Contents

Each archive contains:
- Task JSON files (completed and failed)
- Associated .log files with execution details
- Original timestamps and metadata

## See Also

- [Performance Guide](../PERFORMANCE.md) - Optimization techniques
- [Upgrade Guide](../UPGRADE.md) - Migration instructions
