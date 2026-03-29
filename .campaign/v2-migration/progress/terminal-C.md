---
terminal: C
title: "Phase 4 — Agent framework"
campaign: v2-migration
wave: 2
status: in_progress
branch: feat/phase-4-agent-framework
writes_to:
  - src/searchat/core/connectors/base.py
  - src/searchat/core/connectors/protocols.py
  - src/searchat/core/connectors/claude.py
  - src/searchat/core/connectors/vibe.py
  - src/searchat/core/connectors/codex.py
  - src/searchat/core/connectors/opencode.py
  - src/searchat/core/connectors/gemini.py
  - src/searchat/core/connectors/continue_cli.py
  - src/searchat/core/connectors/cursor.py
  - src/searchat/core/connectors/aider.py
  - src/searchat/core/connectors/registry.py
  - tests/unit/connectors/
issue_refs:
  - "#68"
target: "AgentProviderBase ABC, 4 full + 4 stub implementations, all tests pass"
blocked_by: ["A"]
started: "2026-03-29"
updated: "2026-03-29"
---

# Terminal C — Phase 4: Agent framework unification

## Issues

| Issue | Task | Target | Status | Actual |
|-------|------|--------|--------|--------|
| #68 | Extend connectors with AgentProvider methods | AgentProviderBase ABC + 8 connector updates | done | 8/8 connectors, 104 new tests |

## Results

## Log

- **2026-03-29T00:00** — Started Phase 4. Created branch feat/phase-4-agent-framework from main.
- **2026-03-29T00:01** — AgentProviderBase ABC created, protocol extended with @runtime_checkable, registry gains has_v2_support().
- **2026-03-29T00:02** — All 8 connectors extended: 4 full (claude, vibe, codex, opencode) + 4 stub (gemini, continue, cursor, aider). 1829 tests pass.
- **2026-03-29T00:03** — 104 new tests added (protocol conformance + V2 unit tests). 1933 total tests pass. Ready for PR.
