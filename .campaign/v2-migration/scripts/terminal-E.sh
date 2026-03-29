#!/usr/bin/env bash
cd "/Users/druk/WorkSpace/AetherForge/searchat"
_prompt_file=$(mktemp)
trap 'rm -f "$_prompt_file"; touch "/Users/druk/WorkSpace/AetherForge/searchat/.campaign/v2-migration/.markers/terminal-E.done"' EXIT

cat > "$_prompt_file" <<'PROMPT'
Working on Phase 3 of the Searchat v2 migration: switching all reads from Parquet+FAISS to DuckDB.
Repo: /Users/druk/WorkSpace/AetherForge/searchat
Branch: feat/phase-3-read-cutover (create from main if it doesn't exist, otherwise checkout and continue)

Context:
- Project: Searchat — semantic search and RAG for local AI coding agent conversations
- After prior phases: DuckDB storage (dual-write), unified search engine (6 modes), agent framework all on main
- This phase is a wiring change — no new modules, just switching defaults and factory returns
- Config: src/searchat/config/settings.py — change StorageConfig.backend default from "dual" to "duckdb"
- Storage service: src/searchat/services/storage_service.py
- Retrieval service: src/searchat/services/retrieval_service.py
- API dependencies: src/searchat/api/dependencies.py
- Watcher: src/searchat/core/watcher.py
- Backup system: src/searchat/services/backup.py — needs to snapshot DuckDB file instead of Parquet dir
- Old Parquet read path must NOT be deleted — keep for emergency rollback via config toggle
- Python typing: use built-in generics, | unions, from __future__ import annotations
- Package manager: uv only — NEVER pip

Issue: #69 — Phase 3: Read path cutover to DuckDB

Switch all read operations to DuckDB:

1. Config Default Change:
   - src/searchat/config/settings.py: StorageConfig.backend default "dual" → "duckdb"

2. Service Factory Updates:
   - src/searchat/services/storage_service.py — returns DuckDB-backed UnifiedStorage
   - src/searchat/services/retrieval_service.py — returns UnifiedSearchEngine

3. API Dependencies:
   - src/searchat/api/dependencies.py — DuckDB-backed singletons

4. Watcher:
   - src/searchat/core/watcher.py — callback targets DuckDB indexer

5. Backup System:
   - src/searchat/services/backup.py — BackupManager.create_backup() copies unified.duckdb file
   - Backup manifest gains storage_backend field
   - Old Parquet-based backups remain readable via legacy code path

6. Rollback Verification:
   - Setting backend: "parquet" in config must restore full Parquet read path
   - Test this explicitly

Target: All reads via DuckDB, backup snapshots DuckDB file, config rollback works, all existing tests pass.

CRITICAL FIRST ACTION: Read .campaign/v2-migration/progress/terminal-E.md.
Update its status from PENDING to IN_PROGRESS. After every commit, update this file with:
- Current counts in the Issues table Actual column
- A timestamped log entry describing what changed
This progress file is how other terminals and the operator track your work.

Rules:
- CRITICAL: Parquet files are IRREPLACEABLE — NEVER delete any .parquet or .faiss files
- Safety guards: index_all() RuntimeError and /api/reindex 403 must be preserved in ALL phases
- All 144 existing tests must pass after every commit — run: uv run pytest tests/ -x
- Conventional commits: feat(scope): description
- Push to origin (fork) only — NEVER push to upstream
- No AI attribution in commits
- Python typing: built-in generics, | unions, from __future__ import annotations
- Package manager: uv only (uv add, uv run) — NEVER pip/pip3
- Do NOT modify protected files (see campaign.toml for full list)
- Atomic commits, push after each unit of work
- Update .campaign/v2-migration/progress/terminal-E.md after every commit
- When done: gh issue close 69 --repo Mathews-Tom/searchat

Read CLAUDE.md and .campaign/v2-migration/campaign.toml for full context.
PROMPT
claude --dangerously-skip-permissions "$(cat "$_prompt_file")"
