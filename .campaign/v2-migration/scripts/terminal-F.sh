#!/usr/bin/env bash
cd "/Users/druk/WorkSpace/AetherForge/searchat"
_prompt_file=$(mktemp)
trap 'rm -f "$_prompt_file"; touch "/Users/druk/WorkSpace/AetherForge/searchat/.campaign/v2-migration/.markers/terminal-F.done"' EXIT

cat > "$_prompt_file" <<'PROMPT'
Working on Phase 5 of the Searchat v2 migration: replacing ConversationIndexer with a DuckDB-native UnifiedIndexer.
Repo: /Users/druk/WorkSpace/AetherForge/searchat
Branch: feat/phase-5-unified-indexer (create from main if it doesn't exist, otherwise checkout and continue)

Context:
- Project: Searchat — semantic search and RAG for local AI coding agent conversations
- Upstream v2 indexer: git fetch upstream && git show upstream/main:src/searchat/core/indexer.py (~1539 LOC)
- Current indexer: src/searchat/core/indexer.py (1463 LOC) — has RuntimeError guard on index_all()
- After prior phases: all reads are DuckDB, dual-writer still active for writes
- This phase replaces the write path — UnifiedIndexer writes directly to DuckDB, bypasses dual-writer
- Agent framework (Phase 4) provides AgentProvider methods for exchange-level segmentation
- Daemon: src/searchat/daemon/ghost.py — watcher callback needs to invoke UnifiedIndexer
- API routers: src/searchat/api/routers/indexing.py
- Dependencies: src/searchat/api/dependencies.py — get_indexer()
- Watcher: src/searchat/core/watcher.py
- Phase 0 protocols on main: IndexingBackend in src/searchat/contracts/indexing.py
- Python typing: use built-in generics, | unions, from __future__ import annotations
- Package manager: uv only — NEVER pip

Issue: #70 — Phase 5: Unified indexer

Build the DuckDB-native unified indexer:

1. UnifiedIndexer (port from upstream ~1539 LOC):
   - Implements IndexingBackend protocol
   - Writes directly to DuckDB (no dual-writer)
   - Exchange-level segmentation using AgentProvider.load_messages()
   - Place in: src/searchat/core/unified_indexer.py

2. Deprecate Old Indexer:
   - src/searchat/core/indexer.py — keep safety guard pass-through, mark deprecated
   - src/searchat/storage/dual_writer.py — mark deprecated, bypassed

3. Consumer Updates:
   - src/searchat/api/routers/indexing.py — use unified indexer
   - src/searchat/api/dependencies.py — get_indexer() returns UnifiedIndexer
   - src/searchat/core/watcher.py — callback invokes UnifiedIndexer.index_from_source_files()
   - src/searchat/daemon/ghost.py — use unified indexer

4. Safety Guards (MUST preserve):
   - UnifiedIndexer.index_all() raises RuntimeError (same message as current guard)
   - /api/reindex remains 403

5. Tests:
   - tests/unit/core/test_unified_indexer.py
   - tests/integration/test_unified_indexer.py

Target: UnifiedIndexer with exchange-level segmentation, dual-writer bypassed, safety guards preserved, all existing tests pass.

CRITICAL FIRST ACTION: Read .campaign/v2-migration/progress/terminal-F.md.
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
- Update .campaign/v2-migration/progress/terminal-F.md after every commit
- When done: gh issue close 70 --repo Mathews-Tom/searchat

Read CLAUDE.md and .campaign/v2-migration/campaign.toml for full context.
PROMPT
claude --dangerously-skip-permissions "$(cat "$_prompt_file")"
