#!/usr/bin/env bash
cd "/Users/druk/WorkSpace/AetherForge/searchat"
_prompt_file=$(mktemp)
trap 'rm -f "$_prompt_file"; touch "/Users/druk/WorkSpace/AetherForge/searchat/.campaign/v2-migration/.markers/terminal-C.done"' EXIT

cat > "$_prompt_file" <<'PROMPT'
Working on Phase 4 of the Searchat v2 migration: extending 9 agent connectors with upstream AgentProvider methods.
Repo: /Users/druk/WorkSpace/AetherForge/searchat
Branch: feat/phase-4-agent-framework (create from main if it doesn't exist, otherwise checkout and continue)

Context:
- Project: Searchat — semantic search and RAG for local AI coding agent conversations
- 9 connectors exist: claude.py, vibe.py, codex.py, opencode.py, gemini.py, continue_cli.py, cursor.py, aider.py + utils.py
- Current protocol: src/searchat/core/connectors/protocols.py (AgentConnector)
- Registry: src/searchat/core/connectors/registry.py
- Phase 0 protocols on main: AgentProvider protocol in src/searchat/contracts/agent.py
- Upstream v2 reference: git fetch upstream && git show upstream/main:src/searchat/core/connectors/
- Python typing: use built-in generics, | unions, from __future__ import annotations
- Package manager: uv only — NEVER pip

Issue: #68 — Phase 4: Agent framework unification

Extend the agent connector framework with upstream AgentProvider capabilities:

1. AgentProviderBase ABC:
   - Combines existing AgentConnector protocol + upstream methods
   - New methods: load_messages(), extract_cwd(), build_resume_command()
   - All new methods have default no-op implementations (backward compatible)
   - Place in: src/searchat/core/connectors/base.py

2. Full implementations (port from upstream):
   - claude.py — full load_messages, extract_cwd, build_resume_command
   - vibe.py — full implementations
   - codex.py — full implementations
   - opencode.py — full implementations

3. Stub implementations (fork-only agents, no upstream equivalent):
   - gemini.py — default no-ops
   - continue_cli.py — default no-ops
   - cursor.py — default no-ops
   - aider.py — default no-ops

4. Update protocol and registry:
   - src/searchat/core/connectors/protocols.py — extend AgentConnector with optional methods
   - src/searchat/core/connectors/registry.py — validation accepts new methods

5. Tests:
   - Protocol conformance tests for all 8 connectors
   - Unit tests for full implementations (claude, vibe, codex, opencode)
   - Place in: tests/unit/connectors/

Target: AgentProviderBase ABC defined, 4 full + 4 stub implementations, all existing tests pass.

CRITICAL FIRST ACTION: Read .campaign/v2-migration/progress/terminal-C.md.
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
- Update .campaign/v2-migration/progress/terminal-C.md after every commit
- When done: gh issue close 68 --repo Mathews-Tom/searchat

Read CLAUDE.md and .campaign/v2-migration/campaign.toml for full context.
PROMPT
claude --dangerously-skip-permissions "$(cat "$_prompt_file")"
