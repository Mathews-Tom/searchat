---
terminal: E
title: "Phase 3 — Read path cutover"
campaign: v2-migration
wave: 4
status: complete
branch: feat/phase-3-read-cutover
writes_to:
  - src/searchat/config/settings.py
  - src/searchat/services/storage_service.py
  - src/searchat/services/retrieval_service.py
  - src/searchat/api/dependencies.py
  - src/searchat/core/watcher.py
  - src/searchat/services/backup.py
issue_refs:
  - "#69"
target: "All reads via DuckDB, backup snapshots DuckDB file, config rollback works, all tests pass"
blocked_by: ["B", "D"]
started: "2026-03-29"
updated: "2026-03-29"
---

# Terminal E — Phase 3: Read path cutover

## Issues

| Issue | Task | Target | Status | Actual |
|-------|------|--------|--------|--------|
| #69 | Switch all reads from Parquet to DuckDB | Config default change, factory rewiring, backup update | complete | 4 commits, 12 new tests |

## Results

- **Config defaults**: `DEFAULT_STORAGE_BACKEND` → `"duckdb"`, `DEFAULT_SEARCH_ENGINE` → `"unified"`
- **Storage factory**: `build_storage_service` returns `UnifiedStorage` (read-only) when DuckDB file exists, falls back to `DuckDBStore` (Parquet) when missing or backend="parquet"
- **Retrieval factory**: `build_retrieval_service` defaults to `UnifiedSearchEngine`, legacy `SearchEngine` via `engine="legacy"`
- **Dependencies**: No changes needed — factories handle routing via config
- **Watcher**: No changes needed — uses ConversationIndexer which already dual-writes
- **Backup**: No changes needed (protected file) — `_iter_live_backup_files` already includes DuckDB file under `data/`
- **Rollback**: Setting `storage.backend = "parquet"` + `search.engine = "legacy"` in config restores full Parquet read path
- **Tests**: 2029 passing (12 new), 84.45% coverage

## Log

- **2026-03-29 T0**: Started Phase 3. Branch created from main. 2017 tests passing baseline.
- **2026-03-29 T1**: Config defaults switched (duckdb, unified). Tests pass.
- **2026-03-29 T2**: Storage factory routes to UnifiedStorage when DuckDB exists, Parquet fallback. Fixed 3 test mock configs. Tests pass.
- **2026-03-29 T3**: Retrieval factory defaults to UnifiedSearchEngine. Tests pass.
- **2026-03-29 T4**: Added 12 rollback verification tests. 2029 tests passing. Phase complete.
