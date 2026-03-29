#!/usr/bin/env bash
cd "/Users/druk/WorkSpace/AetherForge/searchat"
_prompt_file=$(mktemp)
trap 'rm -f "$_prompt_file"; touch "/Users/druk/WorkSpace/AetherForge/searchat/.campaign/v2-migration/.markers/terminal-A.done"' EXIT

cat > "$_prompt_file" <<'PROMPT'
Working on Phase 0 of the Searchat v2 migration: inserting protocol-based abstraction seams between consumers and storage/search implementations.
Repo: /Users/druk/WorkSpace/AetherForge/searchat
Branch: feat/phase-0-protocols (create from main if it doesn't exist, otherwise checkout and continue)

Context:
- Project: Searchat — semantic search and RAG for local AI coding agent conversations
- Current architecture: Parquet+FAISS storage, DuckDB for FTS queries, 18 routers + MCP + CLI consume SearchEngine and ConversationIndexer directly
- src/searchat/contracts/ exists but only has __init__.py, errors.py, similarity.py — these are NOT the protocol contracts needed
- Current storage service: src/searchat/services/storage_service.py
- Current retrieval service: src/searchat/services/retrieval_service.py (SemanticRetrievalService)
- Current connector protocol: src/searchat/core/connectors/protocols.py (AgentConnector)
- API dependencies: src/searchat/api/dependencies.py
- 144 test files across tests/
- Upstream v2 reference: git fetch upstream && git show upstream/main:src/searchat/ for v2 patterns
- Python typing: use built-in generics, | unions, from __future__ import annotations
- Package manager: uv only (uv add, uv run) — NEVER pip

Issue: #65 — Phase 0: Abstraction seams & protocol contracts

Define 4 protocol-based abstractions that will allow storage/search/indexing implementations to be swapped without changing 40+ consumer call sites:

1. StorageBackend protocol — superset of current StorageService methods + v2 DuckDB methods
   - Current methods: read conversations, read messages, read file state, etc.
   - V2 methods: DuckDB-native operations (will be used by Phase 1)
   - Place in: src/searchat/contracts/storage.py

2. RetrievalBackend protocol — superset of SemanticRetrievalService + AlgorithmType dispatch
   - Current methods: search (keyword, semantic, hybrid)
   - V2 methods: adaptive, cross_layer, distill (stubs for now)
   - Place in: src/searchat/contracts/retrieval.py

3. IndexingBackend protocol — superset of ConversationIndexer
   - Current methods: index_append_only, rebuild
   - V2 methods: index_from_source_files (exchange-level)
   - Place in: src/searchat/contracts/indexing.py

4. AgentProvider protocol — unifies AgentConnector + upstream ABC methods
   - Current methods: from AgentConnector protocol
   - V2 methods: load_messages, extract_cwd, build_resume_command
   - Place in: src/searchat/contracts/agent.py

After defining protocols:
- Make existing concrete classes conform (StorageService → StorageBackend, SemanticRetrievalService → RetrievalBackend, etc.)
- Update type annotations in src/searchat/api/dependencies.py to use protocol types
- Write protocol conformance tests verifying each concrete class satisfies its protocol

Target: 4 protocol definitions, all concrete classes conform, all 144 existing tests pass with zero behavioral change.

CRITICAL FIRST ACTION: Read .campaign/v2-migration/progress/terminal-A.md.
Update its status from PENDING to IN_PROGRESS. After every commit, update this file with:
- Current counts in the Issues table Actual column
- A timestamped log entry describing what changed
This progress file is how other terminals and the operator track your work.

Rules:
- CRITICAL: Parquet files are IRREPLACEABLE — NEVER delete any .parquet or .faiss files
- Safety guards: index_all() RuntimeError and /api/reindex 403 must be preserved in ALL phases
- All 144 existing tests must pass after every commit — run: uv run pytest tests/ -x
- Conventional commits: feat(scope): description — see .claude/rules/commit-standards.md
- Push to origin (fork) only — NEVER push to upstream
- No AI attribution in commits (no Co-Authored-By, no 'Generated with Claude Code')
- Python typing: built-in generics, | unions, from __future__ import annotations
- Package manager: uv only (uv add, uv run, uv pip list) — NEVER pip/pip3
- Do NOT modify protected files: src/searchat/expertise/, src/searchat/knowledge_graph/, src/searchat/services/bookmarks.py, src/searchat/services/saved_queries.py, src/searchat/services/dashboards.py, src/searchat/services/analytics.py, src/searchat/services/backup.py, src/searchat/services/backup_contracts.py, src/searchat/services/backup_crypto.py, src/searchat/services/chat_service.py, src/searchat/services/export_service.py, src/searchat/services/pattern_mining.py
- Atomic commits, push after each unit of work
- Update .campaign/v2-migration/progress/terminal-A.md after every commit
- When done: gh issue close 65 --repo Mathews-Tom/searchat

Read CLAUDE.md and .campaign/v2-migration/campaign.toml for full context.
PROMPT
claude --dangerously-skip-permissions "$(cat "$_prompt_file")"
