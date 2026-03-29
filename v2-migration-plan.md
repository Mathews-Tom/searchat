# Searchat v2 Migration Plan: Parquet+FAISS → DuckDB Unified Architecture

## Context

The upstream repo (`Process-Point-Technologies-Corporation/searchat`) has evolved significantly since our fork diverged at `0ca5e52`. Three major commits landed:
1. **v2 architecture** (`24d626b`) — unified DuckDB storage, exchange-level search, Memory Palace, agent framework
2. **Test fixes** (`941744d`) — DuckDB cursor isolation, provider defaults
3. **Rust hybrid port** (`6dd425a`) — rejected for our fork (too much Python surface to port)

Our fork added ~72K lines across 15+ features (expertise, knowledge graph, 9 connectors, MCP, analytics, etc.). The core storage/search layer diverged: we extended Parquet+FAISS, upstream replaced it with DuckDB unified. This plan migrates our fork to the v2 DuckDB architecture while preserving every fork feature.

**Key constraint**: Source JSONLs are LOST. Parquet files contain IRREPLACEABLE data. Every storage operation must be non-destructive with verified rollback.

---

## Architecture: Before → After

| Layer | Current (v0.6.2) | After (v0.7.0) |
|-------|-------------------|-----------------|
| Primary storage | Parquet files + PyArrow | DuckDB unified (single file) |
| Vector search | FAISS IndexFlatL2 (384-dim) | DuckDB HNSW (VSS extension) |
| Keyword search | DuckDB FTS over Parquet | DuckDB FTS (native tables) |
| Search granularity | Chunk-level (1500 chars) | Exchange-level (conversation turns) |
| Search modes | 3 (keyword, semantic, hybrid) | 6 (+adaptive, cross-layer, distill) |
| Weight tuning | Fixed 60/40 | Adaptive per-query via QueryClassifier |
| Agent framework | 9 connectors (AgentConnector protocol) | 9 connectors (AgentProvider ABC) |
| Distillation | None | Memory Palace (LLM-powered) |

---

## Dependency Graph

```
Phase 0 (Protocols)
  ├──→ Phase 1 (DuckDB Dual-Write) ──→ Phase 3 (Read Cutover) ──→ Phase 5 (Unified Indexer)
  ├──→ Phase 2 (Search Upgrade) ──→ Phase 3 ──→ Phase 6 (Palace)        ↑
  └──→ Phase 4 (Agent Framework) ─────────────────────────────────────────┘
                                                                          ↓
                                                                   Phase 7 (Cleanup)
                                                                          ↓
                                                                   Phase 8 (ONNX, future)
```

**Parallelizable**: Phases 2 and 4 (both depend only on Phase 0).

---

## Phase 0: Abstraction Seams & Protocol Contracts

**Complexity: M | ~3-4 days | Deps: None**

### What & Why
Insert protocol-based abstractions between consumers and storage/search implementations. Currently `SearchEngine` and `ConversationIndexer` are directly consumed by 18 routers, MCP, CLI, daemon, expertise, and KG. Without seams, any storage change propagates to 40+ call sites.

### Files Created
- `src/searchat/contracts/__init__.py`
- `src/searchat/contracts/storage.py` — `StorageBackend` protocol (superset of current `StorageService` + v2 methods)
- `src/searchat/contracts/retrieval.py` — `RetrievalBackend` protocol (superset of `SemanticRetrievalService` + `AlgorithmType` dispatch)
- `src/searchat/contracts/indexing.py` — `IndexingBackend` protocol
- `src/searchat/contracts/agent.py` — `AgentProvider` protocol (unifies `AgentConnector` + upstream ABC)

### Files Modified
- `src/searchat/services/retrieval_service.py` — `SemanticRetrievalService` (line 45) extends `RetrievalBackend`
- `src/searchat/services/storage_service.py` — extends `StorageBackend`
- `src/searchat/core/connectors/protocols.py` — `AgentConnector` (line 11) extends `AgentProvider`
- `src/searchat/api/dependencies.py` — type annotations switch to protocol types

### Test Plan
- All 144 existing tests pass (zero behavioral change)
- New: protocol conformance tests for each concrete class

### Risk: **Low.** Pure structural typing refactor. Rollback = revert protocol files.

---

## Phase 1: DuckDB Unified Storage (Dual-Write)

**Complexity: XL | ~10-14 days | Deps: Phase 0**

### What & Why
Introduce `UnifiedStorage` as a DuckDB-backed storage backend running **in parallel** with Parquet+FAISS. All writes go to both systems. All reads still from Parquet. This proves the DuckDB schema and data migration are lossless before switching reads.

### Core Design: Dual-Write Strategy
Because source JSONLs are lost, we never delete old data:
1. Dual-writer proxy writes every operation to both backends
2. Verification tool compares stores row-by-row and vector-by-vector
3. Config toggle `storage.backend: "parquet" | "duckdb" | "dual"` (default: `"dual"`)

### DuckDB Schema (from upstream)
Tables: `conversations`, `messages`, `exchanges`, `verbatim_embeddings`, `source_file_state`, `code_blocks`
Extensions: VSS (HNSW vector search), FTS (BM25 keyword search)
Thread safety: thread-local write cursors, fresh read cursors

### Files Created
- `src/searchat/storage/__init__.py`
- `src/searchat/storage/unified_storage.py` — port of upstream (2360 LOC), adapted to our schemas
- `src/searchat/storage/schema.py` — DDL definitions, version tracking
- `src/searchat/storage/migration_v1_to_v2.py` — one-time Parquet→DuckDB ETL
- `src/searchat/storage/dual_writer.py` — proxy writing to both backends
- `src/searchat/cli/migrate_storage.py` — `searchat migrate-storage [--dry-run|--verify|--rollback]`
- `tests/unit/storage/test_unified_storage.py`
- `tests/integration/test_migration_v1_to_v2.py`
- `tests/integration/test_dual_writer.py`

### Files Modified
- `src/searchat/core/indexer.py` — inject dual-writer after Parquet+FAISS writes
- `src/searchat/config/settings.py` — add `StorageConfig(backend="dual")`, HNSW params
- `src/searchat/config/constants.py` — DuckDB paths, HNSW defaults
- `pyproject.toml` — add `duckdb[vss]` dependency

### Data Migration Steps
1. `searchat migrate-storage --dry-run` — scan parquets, estimate row counts
2. `searchat migrate-storage` — ETL:
   - Read conversation parquets → `conversations` + `messages` tables
   - Read embeddings metadata parquet → `verbatim_embeddings`
   - Extract FAISS vectors via `faiss.reconstruct_n()` → HNSW table
   - Read `file_state.parquet` → `source_file_state`
   - Derive exchanges from message arrays (exchange-level segmentation)
3. `searchat migrate-storage --verify` — row count comparison, 100 random conversation diffs, 50 random vector L2 distance comparisons
4. Original Parquet/FAISS files **NEVER deleted**

### Safety Guards Preserved
- `index_all()` RuntimeError (indexer.py:283) remains
- `/api/reindex` 403 guard remains
- Dual-writer respects the same safety contract

### Risk: **High** (data migration). Mitigations: `--dry-run`, `--verify`, config toggle rollback, Parquet files never deleted.
Git tag: `v0.7.0-alpha.2`

---

## Phase 2: Search Engine Upgrade (3 → 6 Modes + Adaptive)

**Complexity: L | ~7-10 days | Deps: Phase 1**

### What & Why
Replace `SearchEngine` (346 LOC, fixed 60/40 weights) with `UnifiedSearchEngine` (6 algorithm types + adaptive weight selection). Adds QueryClassifier, ResultMerger with CombMNZ fusion, and ProgressiveFallback.

### New Search Capabilities
| Mode | Source | Behavior |
|------|--------|----------|
| KEYWORD | Upstream | BM25 via DuckDB FTS |
| SEMANTIC | Upstream | HNSW cosine via DuckDB VSS |
| HYBRID | Both | Weighted fusion (configurable) |
| ADAPTIVE | Upstream | QueryClassifier picks weights per query |
| CROSS_LAYER | Upstream | Palace + verbatim merge (stubbed until Phase 6) |
| DISTILL | Upstream | Palace objects only (stubbed until Phase 6) |

### Files Created
- `src/searchat/core/unified_search.py` — port of upstream (1213 LOC)
- `src/searchat/core/query_classifier.py` — port (162 LOC)
- `src/searchat/core/result_merger.py` — port (283 LOC), CombMNZ + percentile normalization
- `src/searchat/core/progressive_fallback.py` — port (238 LOC), 3-tier fallback
- `src/searchat/core/conversation_filter.py` — port (179 LOC), excludes automated conversations
- Tests for each

### Files Modified
- `src/searchat/models/enums.py` — add `AlgorithmType` enum (6 values), keep `SearchMode` as alias
- `src/searchat/models/domain.py` — extend `SearchResult` with `exchange_id`, `exchange_text`, `bm25_score`, `semantic_score` (optional, backward compat)
- `src/searchat/config/settings.py` — add `RankingConfig` (intersection_boost, weights, bm25 params)
- `src/searchat/services/retrieval_service.py` — `build_retrieval_service()` returns `UnifiedSearchEngine` when backend=duckdb
- `src/searchat/api/routers/search.py` — accept `algorithm` param, map legacy `mode=hybrid` to `AlgorithmType.HYBRID`

### Backward Compatibility
- `SearchMode.KEYWORD/SEMANTIC/HYBRID` still valid, map to `AlgorithmType` equivalents
- `GET /api/search?mode=hybrid` continues working
- CROSS_LAYER/DISTILL return 400 until Phase 6

### Risk: **Medium.** Config toggle `search.engine: "legacy"` falls back to old SearchEngine. Both coexist via protocol layer.
Git tag: `v0.7.0-alpha.3`

---

## Phase 3: Read Path Cutover to DuckDB

**Complexity: M | ~5-7 days | Deps: Phase 1 + Phase 2**

### What & Why
Switch all reads from Parquet+FAISS to DuckDB. Dual-writer continues. Old Parquet read path becomes dead code but is NOT deleted (emergency rollback).

### Files Modified
- `src/searchat/config/settings.py` — change `StorageConfig.backend` default: `"dual"` → `"duckdb"`
- `src/searchat/services/storage_service.py` — returns DuckDB-backed `UnifiedStorage`
- `src/searchat/services/retrieval_service.py` — returns `UnifiedSearchEngine`
- `src/searchat/api/dependencies.py` — DuckDB-backed singletons
- `src/searchat/core/watcher.py` — callback targets DuckDB indexer
- `src/searchat/services/backup.py` — snapshot DuckDB file instead of Parquet dir

### Backup System Update
- `BackupManager.create_backup()` copies `unified.duckdb` file
- Backup manifest gains `storage_backend` field
- Old backups (Parquet-based) remain readable via legacy code path

### Risk: **Medium.** Rollback = `backend: "parquet"` in config.
Git tag: `v0.7.0-beta.1`

---

## Phase 4: Agent Framework Unification

**Complexity: M | ~5-7 days | Deps: Phase 0 (parallel with Phase 2)**

### What & Why
Extend our 9 connectors with upstream's `AgentProvider` methods: `load_messages()`, `extract_cwd()`, `build_resume_command()`. These enable exchange-level indexing and conversation filtering.

### Approach
- Add `AgentProviderBase` ABC that combines our `AgentConnector` + upstream methods
- Existing methods unchanged; new methods have default no-op implementations
- Claude, Vibe, Codex, OpenCode get full implementations (ported from upstream)
- Gemini, Continue, Cursor, Aider get stubs (fork-only agents, implement later)
- Entry point registry preserved

### Files Created
- `src/searchat/core/connectors/base.py` — `AgentProviderBase` ABC

### Files Modified
- `src/searchat/core/connectors/protocols.py` — extend `AgentConnector` with optional methods
- All 8 connector files — add new methods (full or stub)
- `src/searchat/core/connectors/registry.py` — validation accepts new methods

### Risk: **Low.** All new methods have default implementations. Existing behavior unchanged.
Git tag: `v0.7.0-alpha.4`

---

## Phase 5: Unified Indexer

**Complexity: L | ~7-10 days | Deps: Phase 3 + Phase 4**

### What & Why
Replace `ConversationIndexer` (1490 LOC) with `UnifiedIndexer` writing directly to DuckDB. Supports exchange-level segmentation, unified agent framework. Remove dual-writer.

### Files Created
- `src/searchat/core/unified_indexer.py` — port of upstream (1539 LOC)
- Tests: unit + integration

### Files Modified
- `src/searchat/core/indexer.py` — deprecated, safety guard pass-through preserved
- `src/searchat/storage/dual_writer.py` — deprecated
- `src/searchat/api/routers/indexing.py` — use unified indexer
- `src/searchat/api/dependencies.py` — `get_indexer()` returns `UnifiedIndexer`
- `src/searchat/core/watcher.py` — callback invokes `UnifiedIndexer.index_from_source_files()`
- `src/searchat/daemon/ghost.py` — use unified indexer

### Safety Guards
- `UnifiedIndexer.index_all()` raises RuntimeError (same message as current guard)
- `/api/reindex` remains 403

### Risk: **Medium.** Rollback = revert to Phase 3 dual-writer state.
Git tag: `v0.7.0-beta.2`

---

## Phase 6: Memory Palace / Distillation System

**Complexity: L | ~7-10 days | Deps: Phase 2 + Phase 5**

### What & Why
Port the upstream Memory Palace: LLM-powered distillation of conversations into searchable knowledge objects. Enables CROSS_LAYER and DISTILL search modes (stubbed since Phase 2). Complements our existing Expertise system (different purpose: palace = compressed memory, expertise = skill extraction).

### Files Created
- `src/searchat/palace/__init__.py`
- `src/searchat/palace/distiller.py` — port (686 LOC), uses our `llm_service` (LiteLLM)
- `src/searchat/palace/storage.py` — port (453 LOC), DuckDB tables
- `src/searchat/palace/query.py` — port (330 LOC), hybrid search on distilled objects
- `src/searchat/palace/faiss_index.py` — port (111 LOC), FAISS for palace vectors (separate from main HNSW)
- `src/searchat/palace/bm25_index.py` — port (125 LOC)
- `src/searchat/palace/facets.py` — port (402 LOC), hierarchical facets
- `src/searchat/cli/distill_cmd.py` — `searchat distill` CLI
- `src/searchat/api/routers/palace.py` — palace API endpoints

### Files Modified
- `src/searchat/core/unified_search.py` — enable CROSS_LAYER/DISTILL (remove 400 stubs)
- `src/searchat/config/settings.py` — add `DistillationConfig`, `PalaceConfig`
- `src/searchat/api/app.py` — register palace router
- `src/searchat/api/dependencies.py` — palace singletons
- `src/searchat/models/domain.py` — add `DistilledObject`, `Room`, `RoomObject`, `PalaceSearchResult`
- `src/searchat/mcp/tools.py` — add palace search tool

### Opt-in
Palace is gated behind `palace.enabled: false` by default. Users run `searchat distill` to populate.

### Risk: **Medium.** Entirely new feature, opt-in config. Rollback = disable config flag.
Git tag: `v0.7.0-rc.1`

---

## Phase 7: Cleanup + API Updates + Config Harmonization

**Complexity: M | ~5-7 days | Deps: All prior phases**

### What & Why
Remove deprecated scaffolding, harmonize config with upstream, update API responses for v2 fields, update MCP tools, move `faiss-cpu` to optional dependency.

### Files Deleted
- `src/searchat/storage/dual_writer.py`
- `src/searchat/core/search_engine.py` (old Parquet+FAISS engine)
- `src/searchat/services/duckdb_storage.py` (old DuckDB-over-Parquet)
- `src/searchat/storage/migration_v1_to_v2.py` (one-time migration, done)

### Files Preserved (fork-only, untouched throughout)
- `src/searchat/expertise/` — entire expertise store
- `src/searchat/knowledge_graph/` — entire KG store
- `src/searchat/services/bookmarks.py`, `saved_queries.py`, `dashboards.py`, `analytics.py`
- `src/searchat/services/backup.py` + `backup_contracts.py` + `backup_crypto.py`
- `src/searchat/services/chat_service.py`, `export_service.py`, `pattern_mining.py`

### Dependency Changes
- `pyproject.toml`: move `faiss-cpu` to optional `[palace]` extra, `pyarrow` to optional `[legacy]`

### Risk: **Low.** Cleanup only.
Git tag: `v0.7.0` (release)

---

## Phase 8 (Future): ONNX Embedding Optimization

**Outline only.** Replace `sentence-transformers` (PyTorch) with `onnxruntime` for inference. Use upstream's `scripts/export_onnx.py` to convert all-MiniLM-L6-v2. Config: `embedding.backend: "onnx" | "sentence-transformers"`. Expected 2-5x CPU speedup, ~10x memory reduction.

---

## Fork Feature Preservation Matrix

| Feature | Storage Dep | Migration Impact | Phase |
|---------|-------------|------------------|-------|
| Expertise Store | Own DuckDB | **None** | — |
| Knowledge Graph | Own DuckDB | **None** | — |
| MCP Server (20+ tools) | RetrievalService | Transparent via protocols | 0, 7 |
| Bookmarks | Own storage | **None** | — |
| Saved Queries | Own storage | **None** | — |
| Dashboards | Analytics + Storage | Transparent via protocols | 0 |
| Analytics | Own storage | **None** | — |
| Backup/Crypto | Parquet snapshot | Snapshot DuckDB file instead | 3 |
| Chat (RAG) | RetrievalService | Transparent | 0 |
| Pattern Mining | Storage queries | Update to DuckDB queries | 3 |
| Code Search | Code parquets | Migrate to DuckDB table | 1 |
| Daemon/Ghost | Watcher + Indexer | Update to unified indexer | 5 |
| CLI REPL | SearchEngine | Update to unified search | 2 |
| 9 Connectors | AgentConnector | Extend with AgentProvider methods | 4 |

---

## Timeline

| Phase | Complexity | Duration | Parallel? |
|-------|-----------|----------|-----------|
| 0: Protocols | M | 3-4 days | — |
| 1: DuckDB Dual-Write | XL | 10-14 days | — |
| 2: Search Upgrade | L | 7-10 days | ∥ with Phase 4 |
| 4: Agent Framework | M | 5-7 days | ∥ with Phase 2 |
| 3: Read Cutover | M | 5-7 days | — |
| 5: Unified Indexer | L | 7-10 days | — |
| 6: Palace | L | 7-10 days | — |
| 7: Cleanup | M | 5-7 days | — |

**Total: ~9 weeks** to full v2 architecture.

## Version Tags

- `v0.7.0-alpha.1` → Phase 0 (protocols)
- `v0.7.0-alpha.2` → Phase 1 (dual-write)
- `v0.7.0-alpha.3` → Phase 2 (search upgrade)
- `v0.7.0-alpha.4` → Phase 4 (agents)
- `v0.7.0-beta.1` → Phase 3 (read cutover)
- `v0.7.0-beta.2` → Phase 5 (unified indexer)
- `v0.7.0-rc.1` → Phase 6 (palace)
- `v0.7.0` → Phase 7 (release)

## Verification Strategy

After each phase:
1. All existing 144 tests pass
2. `searchat-web` starts and serves search results
3. Manual smoke test: search 3 known queries, verify results match pre-migration baseline
4. `git diff main` reviewed for unintended changes to fork-only features
