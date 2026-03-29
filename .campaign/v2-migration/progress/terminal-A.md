---
terminal: A
title: "Phase 0 — Protocol contracts"
campaign: v2-migration
wave: 1
status: done
branch: feat/phase-0-protocols
writes_to:
  - src/searchat/contracts/
  - src/searchat/services/retrieval_service.py
  - src/searchat/services/storage_service.py
  - src/searchat/core/connectors/protocols.py
  - src/searchat/api/dependencies.py
  - tests/unit/contracts/
issue_refs:
  - "#65"
target: "4 protocol definitions, all concrete classes conform, 144 tests pass"
blocked_by: []
started: 2026-03-29T00:00:00Z
updated: 2026-03-29T00:00:00Z
---

# Terminal A — Phase 0: Protocol contracts

## Issues

| Issue | Task | Target | Status | Actual |
|-------|------|--------|--------|--------|
| #65 | Define StorageBackend, RetrievalBackend, IndexingBackend, AgentProvider protocols | 4 protocols, conformance tests, 144 tests pass | done | 4 protocols, 4 conformance tests, 1829 tests pass |

## Results

- 4 protocol contracts: `StorageBackend`, `RetrievalBackend`, `IndexingBackend`, `AgentProvider`
- 4 conformance tests: DuckDBStore, SearchEngine, ConversationIndexer, ClaudeConnector
- API dependencies updated to use protocol types
- 1829 tests pass (1825 existing + 4 new conformance)

## Log

- 2026-03-29: Created branch, defined 4 protocols in src/searchat/contracts/, wrote conformance tests, updated dependencies.py to use protocol types. All 1829 tests pass. Pushed a0ab286.
