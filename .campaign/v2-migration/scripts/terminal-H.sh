#!/usr/bin/env bash
cd "/Users/druk/WorkSpace/AetherForge/searchat"
_prompt_file=$(mktemp)
trap 'rm -f "$_prompt_file"; touch "/Users/druk/WorkSpace/AetherForge/searchat/.campaign/v2-migration/.markers/terminal-H.done"' EXIT

cat > "$_prompt_file" <<'PROMPT'
Working on Phase 7 of the Searchat v2 migration: removing deprecated scaffolding, harmonizing config, releasing v0.7.0.
Repo: /Users/druk/WorkSpace/AetherForge/searchat
Branch: feat/phase-7-cleanup (create from main if it doesn't exist, otherwise checkout and continue)

Context:
- Project: Searchat — semantic search and RAG for local AI coding agent conversations
- After all prior phases: DuckDB is sole storage, unified search + indexer active, palace operational
- Files to DELETE: src/searchat/storage/dual_writer.py, src/searchat/core/search_engine.py, src/searchat/services/duckdb_storage.py, src/searchat/storage/migration_v1_to_v2.py
- Dependency changes needed in pyproject.toml: faiss-cpu → optional [palace], pyarrow → optional [legacy]
- Fork-only features that MUST still work after cleanup: expertise, knowledge_graph, bookmarks, saved_queries, dashboards, analytics, backup, backup_contracts, backup_crypto, chat_service, export_service, pattern_mining
- MCP tools: src/searchat/mcp/tools.py — update for v2 fields
- Config: src/searchat/config/settings.py — harmonize with upstream v2 schema
- Python typing: use built-in generics, | unions, from __future__ import annotations
- Package manager: uv only — NEVER pip

Issue: #72 — Phase 7: Cleanup + API updates + config harmonization

Final cleanup and release:

1. Delete Deprecated Files:
   - src/searchat/storage/dual_writer.py
   - src/searchat/core/search_engine.py (old Parquet+FAISS engine)
   - src/searchat/services/duckdb_storage.py (old DuckDB-over-Parquet)
   - src/searchat/storage/migration_v1_to_v2.py (one-time migration, done)

2. Dependency Reshuffling (pyproject.toml):
   - Move faiss-cpu to optional [palace] extra
   - Move pyarrow to optional [legacy] extra
   - Verify all imports still resolve with default install

3. Config Harmonization:
   - Remove deprecated config paths (dual-write toggle, legacy search toggle)
   - Clean up settings.py to reflect final v2 schema

4. API Response Updates:
   - Ensure v2 fields (exchange_id, exchange_text, algorithm type) in search responses

5. MCP Tool Updates:
   - src/searchat/mcp/tools.py — update for v2 search capabilities

6. Fork Feature Verification:
   - Run full test suite
   - Verify all protected features still functional
   - Smoke test: searchat-web starts, search returns results

7. Version and Tag:
   - Update version in pyproject.toml: "0.6.2" → "0.7.0"
   - git tag v0.7.0

Target: Deprecated files deleted, deps reshuffled, config harmonized, all fork features work, v0.7.0 tagged, all tests pass.

CRITICAL FIRST ACTION: Read .campaign/v2-migration/progress/terminal-H.md.
Update its status from PENDING to IN_PROGRESS. After every commit, update this file with:
- Current counts in the Issues table Actual column
- A timestamped log entry describing what changed
This progress file is how other terminals and the operator track your work.

Rules:
- CRITICAL: Parquet files are IRREPLACEABLE — NEVER delete any .parquet or .faiss files
- Safety guards: index_all() RuntimeError and /api/reindex 403 must be preserved in ALL phases
- All existing tests must pass after every commit — run: uv run pytest tests/ -x
- Conventional commits: feat(scope): description
- Push to origin (fork) only — NEVER push to upstream
- No AI attribution in commits
- Python typing: built-in generics, | unions, from __future__ import annotations
- Package manager: uv only (uv add, uv run) — NEVER pip/pip3
- Do NOT modify protected files (see campaign.toml for full list)
- Atomic commits, push after each unit of work
- Update .campaign/v2-migration/progress/terminal-H.md after every commit
- When done: gh issue close 72 --repo Mathews-Tom/searchat

Read CLAUDE.md and .campaign/v2-migration/campaign.toml for full context.
PROMPT
claude --dangerously-skip-permissions "$(cat "$_prompt_file")"
