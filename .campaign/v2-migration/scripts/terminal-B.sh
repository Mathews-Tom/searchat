#!/usr/bin/env bash
cd "/Users/druk/WorkSpace/AetherForge/searchat"
_prompt_file=$(mktemp)
trap 'rm -f "$_prompt_file"; touch "/Users/druk/WorkSpace/AetherForge/searchat/.campaign/v2-migration/.markers/terminal-B.done"' EXIT

cat > "$_prompt_file" <<'PROMPT'
Working on Phase 1 of the Searchat v2 migration: introducing DuckDB-backed UnifiedStorage running in parallel with Parquet+FAISS via a dual-write proxy.
Repo: /Users/druk/WorkSpace/AetherForge/searchat
Branch: feat/phase-1-duckdb-dual-write (create from main if it doesn't exist, otherwise checkout and continue)

Context:
- Project: Searchat — semantic search and RAG for local AI coding agent conversations
- Current storage: Parquet files + PyArrow reads + FAISS IndexFlatL2 (384-dim vectors)
- DuckDB is already a dependency (v1.4.3) — currently used for FTS queries over Parquet
- Upstream v2 code available: git fetch upstream && git show upstream/main:src/searchat/storage/unified_storage.py
- Phase 0 protocols are on main: StorageBackend, IndexingBackend protocols in src/searchat/contracts/
- Config file: src/searchat/config/settings.py
- Current indexer: src/searchat/core/indexer.py (1463 LOC) — line ~283 has index_all() RuntimeError guard
- Data location: ~/.searchat/ (parquet files, FAISS index)
- SOURCE JSONLs ARE LOST — Parquet files contain IRREPLACEABLE data
- Python typing: use built-in generics, | unions, from __future__ import annotations
- Package manager: uv only — NEVER pip

Issue: #66 — Phase 1: DuckDB unified storage with dual-write

Build the DuckDB unified storage layer running in parallel with existing Parquet+FAISS:

1. DuckDB Schema (port from upstream):
   - Tables: conversations, messages, exchanges, verbatim_embeddings, source_file_state, code_blocks
   - Extensions: VSS (HNSW vector search), FTS (BM25 keyword search)
   - Thread safety: thread-local write cursors, fresh read cursors
   - Place in: src/searchat/storage/schema.py

2. UnifiedStorage (port from upstream ~2360 LOC, adapt to our schemas):
   - Implements StorageBackend protocol from Phase 0
   - DuckDB-native CRUD operations
   - Place in: src/searchat/storage/unified_storage.py

3. Dual-Writer Proxy:
   - Writes every operation to both Parquet+FAISS AND DuckDB backends
   - All reads still from Parquet (unchanged)
   - Place in: src/searchat/storage/dual_writer.py

4. Migration ETL (one-time Parquet→DuckDB):
   - Read conversation parquets → conversations + messages tables
   - Read embeddings metadata parquet → verbatim_embeddings
   - Extract FAISS vectors via faiss.reconstruct_n() → HNSW table
   - Read file_state.parquet → source_file_state
   - Derive exchanges from message arrays (exchange-level segmentation)
   - Place in: src/searchat/storage/migration_v1_to_v2.py

5. CLI Command:
   - searchat migrate-storage --dry-run (scan, estimate, no modification)
   - searchat migrate-storage (perform ETL)
   - searchat migrate-storage --verify (row count + random sample diffs)
   - searchat migrate-storage --rollback (disable DuckDB backend in config)
   - Place in: src/searchat/cli/migrate_storage.py

6. Config Toggle:
   - storage.backend: "parquet" | "duckdb" | "dual" (default: "dual")
   - Add to src/searchat/config/settings.py
   - HNSW params: ef_construction, ef_search, M

7. Safety:
   - index_all() RuntimeError guard PRESERVED
   - /api/reindex 403 guard PRESERVED
   - Original Parquet/FAISS files NEVER deleted
   - Dual-writer respects the same safety contract

8. Tests:
   - tests/unit/storage/test_unified_storage.py
   - tests/integration/test_migration_v1_to_v2.py
   - tests/integration/test_dual_writer.py

Target: DuckDB schema created, dual-writer operational, ETL migration with --dry-run/--verify, all existing tests pass.

CRITICAL FIRST ACTION: Read .campaign/v2-migration/progress/terminal-B.md.
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
- Update .campaign/v2-migration/progress/terminal-B.md after every commit
- When done: gh issue close 66 --repo Mathews-Tom/searchat

Read CLAUDE.md and .campaign/v2-migration/campaign.toml for full context.
PROMPT
claude --dangerously-skip-permissions "$(cat "$_prompt_file")"
