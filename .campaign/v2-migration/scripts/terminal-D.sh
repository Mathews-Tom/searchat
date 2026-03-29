#!/usr/bin/env bash
cd "/Users/druk/WorkSpace/AetherForge/searchat"
_prompt_file=$(mktemp)
trap 'rm -f "$_prompt_file"; touch "/Users/druk/WorkSpace/AetherForge/searchat/.campaign/v2-migration/.markers/terminal-D.done"' EXIT

cat > "$_prompt_file" <<'PROMPT'
Working on Phase 2 of the Searchat v2 migration: replacing the search engine with a 6-mode unified search engine with adaptive weight selection.
Repo: /Users/druk/WorkSpace/AetherForge/searchat
Branch: feat/phase-2-search-upgrade (create from main if it doesn't exist, otherwise checkout and continue)

Context:
- Project: Searchat — semantic search and RAG for local AI coding agent conversations
- Current search engine: src/searchat/core/search_engine.py (766 LOC, fixed 60/40 hybrid weights)
- Models: src/searchat/models/enums.py (SearchMode enum), src/searchat/models/domain.py (SearchResult)
- Upstream v2 search code: git fetch upstream && git show upstream/main:src/searchat/core/search_engine.py
- DuckDB dual-write from Phase 1 is on main — DuckDB backend available for FTS/VSS queries
- Agent framework from Phase 4 is on main — AgentProvider methods available
- Search API: src/searchat/api/routers/search.py
- Phase 0 protocols on main: RetrievalBackend in src/searchat/contracts/retrieval.py
- Config: src/searchat/config/settings.py
- Python typing: use built-in generics, | unions, from __future__ import annotations
- Package manager: uv only — NEVER pip

Issue: #67 — Phase 2: Search engine upgrade (3 → 6 modes + adaptive)

Build the unified search engine with 6 algorithm types:

1. UnifiedSearchEngine (port from upstream ~1213 LOC):
   - Implements RetrievalBackend protocol
   - 6 algorithm types: KEYWORD, SEMANTIC, HYBRID, ADAPTIVE, CROSS_LAYER (stubbed), DISTILL (stubbed)
   - Place in: src/searchat/core/unified_search.py

2. QueryClassifier (port ~162 LOC):
   - Classifies queries to select optimal weights for ADAPTIVE mode
   - Place in: src/searchat/core/query_classifier.py

3. ResultMerger (port ~283 LOC):
   - CombMNZ fusion with percentile normalization
   - Place in: src/searchat/core/result_merger.py

4. ProgressiveFallback (port ~238 LOC):
   - 3-tier fallback for degraded-mode resilience
   - Place in: src/searchat/core/progressive_fallback.py

5. ConversationFilter (port ~179 LOC):
   - Excludes automated conversations from results
   - Place in: src/searchat/core/conversation_filter.py

6. Model Updates:
   - src/searchat/models/enums.py — add AlgorithmType enum (6 values), keep SearchMode as alias
   - src/searchat/models/domain.py — extend SearchResult with exchange_id, exchange_text, bm25_score, semantic_score (optional fields, backward compat)

7. Config:
   - src/searchat/config/settings.py — add RankingConfig (intersection_boost, weights, bm25 params)
   - search.engine: "legacy" | "unified" config toggle for rollback

8. API Backward Compatibility:
   - src/searchat/api/routers/search.py — accept algorithm param
   - Legacy mode=hybrid maps to AlgorithmType.HYBRID
   - CROSS_LAYER and DISTILL return 400 until Phase 6

9. Service Wiring:
   - src/searchat/services/retrieval_service.py — build_retrieval_service() returns UnifiedSearchEngine when backend=duckdb

Target: 6 algorithm types, QueryClassifier, CombMNZ fusion, backward-compatible API, all existing tests pass.

CRITICAL FIRST ACTION: Read .campaign/v2-migration/progress/terminal-D.md.
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
- Update .campaign/v2-migration/progress/terminal-D.md after every commit
- When done: gh issue close 67 --repo Mathews-Tom/searchat

Read CLAUDE.md and .campaign/v2-migration/campaign.toml for full context.
PROMPT
claude --dangerously-skip-permissions "$(cat "$_prompt_file")"
