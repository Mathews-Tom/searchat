#!/usr/bin/env bash
cd "/Users/druk/WorkSpace/AetherForge/searchat"
_prompt_file=$(mktemp)
trap 'rm -f "$_prompt_file"; touch "/Users/druk/WorkSpace/AetherForge/searchat/.campaign/v2-migration/.markers/terminal-G.done"' EXIT

cat > "$_prompt_file" <<'PROMPT'
Working on Phase 6 of the Searchat v2 migration: porting the upstream Memory Palace LLM-powered distillation system.
Repo: /Users/druk/WorkSpace/AetherForge/searchat
Branch: feat/phase-6-memory-palace (create from main if it doesn't exist, otherwise checkout and continue)

Context:
- Project: Searchat — semantic search and RAG for local AI coding agent conversations
- Upstream palace code: git fetch upstream && git show upstream/main:src/searchat/palace/
- LLM service: src/searchat/services/llm_service.py (LiteLLM-based) — palace distiller uses this
- Existing expertise system: src/searchat/expertise/ — DIFFERENT purpose (skill extraction vs compressed memory). Do NOT modify.
- UnifiedSearchEngine from Phase 2 has CROSS_LAYER/DISTILL stubs returning 400 — this phase enables them
- Palace is opt-in: palace.enabled config flag, users run 'searchat distill' to populate
- API app factory: src/searchat/api/app.py — register palace router
- Dependencies: src/searchat/api/dependencies.py — palace singletons
- Models: src/searchat/models/domain.py — needs DistilledObject, Room, etc.
- MCP tools: src/searchat/mcp/tools.py — add palace search tool
- Python typing: use built-in generics, | unions, from __future__ import annotations
- Package manager: uv only — NEVER pip

Issue: #71 — Phase 6: Memory Palace / distillation system

Port the upstream Memory Palace:

1. Palace Module (port from upstream):
   - src/searchat/palace/__init__.py
   - src/searchat/palace/distiller.py (~686 LOC) — LLM-powered distillation, uses llm_service
   - src/searchat/palace/storage.py (~453 LOC) — DuckDB tables for palace objects
   - src/searchat/palace/query.py (~330 LOC) — hybrid search on distilled objects
   - src/searchat/palace/faiss_index.py (~111 LOC) — FAISS for palace vectors (separate from main HNSW)
   - src/searchat/palace/bm25_index.py (~125 LOC) — BM25 for palace text search
   - src/searchat/palace/facets.py (~402 LOC) — hierarchical facets

2. CLI Command:
   - src/searchat/cli/distill_cmd.py — searchat distill

3. API Router:
   - src/searchat/api/routers/palace.py — palace search and management endpoints

4. Enable Search Modes:
   - src/searchat/core/unified_search.py — remove CROSS_LAYER/DISTILL 400 stubs, wire to palace query

5. Config:
   - src/searchat/config/settings.py — add DistillationConfig, PalaceConfig
   - palace.enabled: false by default

6. Models:
   - src/searchat/models/domain.py — add DistilledObject, Room, RoomObject, PalaceSearchResult

7. MCP:
   - src/searchat/mcp/tools.py — add palace search tool

8. App Registration:
   - src/searchat/api/app.py — register palace router
   - src/searchat/api/dependencies.py — palace singletons

Target: Palace module complete, CROSS_LAYER/DISTILL modes enabled, CLI distill command, opt-in config, all existing tests pass.

CRITICAL FIRST ACTION: Read .campaign/v2-migration/progress/terminal-G.md.
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
- Do NOT modify src/searchat/expertise/ — palace is a separate system
- Atomic commits, push after each unit of work
- Update .campaign/v2-migration/progress/terminal-G.md after every commit
- When done: gh issue close 71 --repo Mathews-Tom/searchat

Read CLAUDE.md and .campaign/v2-migration/campaign.toml for full context.
PROMPT
claude --dangerously-skip-permissions "$(cat "$_prompt_file")"
