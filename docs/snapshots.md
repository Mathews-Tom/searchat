# Read-only Index Snapshots

Searchat supports browsing/searching an existing backup as a read-only "snapshot".
This lets you inspect historical index state without overwriting your active dataset.

## How it works

- Snapshot selection is a request parameter: `snapshot=<backup_dir_name>`
- When snapshot mode is active:
  - reads route to the backup directory as `search_dir`
  - write-like operations are blocked (403)

## UI

In the Web UI sidebar, use the Dataset selector to switch between:

- Active index
- A backup snapshot (read-only)

When a snapshot is selected, the UI shows a banner: "Viewing snapshot: <name> (read-only)".

## What is disabled in snapshot mode

- Indexing (including "Add Missing Conversations")
- Backup create/restore/delete
- Resume session
- Chat and RAG
- Analytics and dashboards

## Configuration

Snapshots are controlled by a feature flag:

- Config: `[snapshots] enabled = true`
- Env: `SEARCHAT_ENABLE_SNAPSHOTS=true|false`
