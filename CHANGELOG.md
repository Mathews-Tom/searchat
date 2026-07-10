# Changelog

All notable changes to this project will be documented in this file.

## 0.7.2
### Fixed
- `searchat --version` (and `searchat-web --version`, and the FastAPI app's reported OpenAPI `version`) printed a stale, hand-maintained `0.7.0` string after the 0.7.1 release — `searchat.__version__` and `config.constants.APP_VERSION` were separate hardcoded duplicates of the `pyproject.toml` version that were missed during the 0.7.1 bump. Both now resolve dynamically from installed package metadata (`importlib.metadata.version("searchat")`), so they can no longer drift from the published version.

## 0.7.1
### Fixed
- Fix a clean-install crash where every `searchat` CLI invocation, including `searchat --version`, raised `ModuleNotFoundError: No module named 'faiss'`. `core/unified_search.py` imported the optional `faiss` package (part of the `palace` extra) unconditionally at module level; the import is now deferred to the one call site that actually needs it, which already degrades to `SemanticSearchUnavailable` on failure.
- Fix `searchat-setup-index` (the first-time-setup entrypoint) requiring the `palace`/`legacy` extras just to build the initial index. It was still using the deprecated Parquet+FAISS `ConversationIndexer`, missed when the rest of the codebase moved to the DuckDB-native `UnifiedIndexer` default. The default/common path (fresh install, or a safe append-only update) now uses `UnifiedIndexer`; only an explicit full rebuild over *existing* data still requires the guarded legacy engine, matching `reingest-sources`.

## 0.7.0
### Architecture
- Migrate default storage/search to a unified DuckDB-native engine (`UnifiedStorage`, `UnifiedIndexer`, `UnifiedSearchEngine` with 6 algorithm types), replacing the legacy Parquet+FAISS path as the default; migration ran via a dual-write ETL to avoid a hard cutover.
- Extend all 8 connectors (Claude Code, Vibe, OpenCode, Codex, Gemini CLI, Continue, Cursor, Aider) plus the new `omp` connector with a shared `AgentProviderBase` and protocol-based abstraction seams.

### Knowledge & Memory
- Add Memory Palace (`palace` extra): FAISS-based distillation/promotion pipeline, `search_palace` MCP tool, `searchat distill` CLI, and cross-layer search.
- Add the L2 Expertise Store: DuckDB-backed extraction pipeline, priority-ranked primer, configurable-decay staleness scoring, contradiction detection with a resolution UI, `searchat expertise`/`contradictions`/`ci-check` CLI commands, and `prime_expertise`/`record_expertise`/`search_expertise` MCP tools.
- Add the L3 Knowledge Graph engine, API endpoints, `searchat` CLI commands, and primer integration.
- Add tiered memory: age-based distillation candidate selection, hot-index eviction of distilled conversations (verified to never touch source Parquet), a lossless `rehydrate_verbatim` promotion path, and distillate results surfaced directly in search with a rehydration affordance.

### Storage Hygiene & Maintenance
- Add `searchat doctor`: DuckDB bloat ratio, backup-redundancy audit, and live-data-size estimation, surfaced via CLI and `/api/health`.
- Add `searchat rebuild-derived`, which rebuilds FTS/HNSW indexes from already-indexed Parquet data with zero source-file access; `reingest-sources` (the guarded, source-rescanning path) is unchanged and now clearly distinguished in docs and CLI help.
- Add `searchat compact`: verified copy-compaction that runs as an isolated subprocess with a configurable timeout, auto-triggered on graceful shutdown once the bloat ratio crosses a threshold.
- Add `searchat disk`: per-connector disk-usage accounting, indexed-vs-unindexed delta, and Searchat's own storage footprint, surfaced in a new disk dashboard UI panel.
- Add report-only cruft detection (known non-conversation heavyweight artifacts — tool logs, plugin dirs, caches) surfaced in the disk dashboard and CLI; never deletes or modifies matches.
- Add source lifecycle management (`searchat sources archive`/`prune`): checksum + message-count verification (`verify_ingested`), a reversibility proof (`verify_roundtrip`) before any destructive step, zstd archive-in-place, a prune tombstone log, and per-agent/age policy gates (dry-run by default).
- Add `export_original` round-trip support to every connector, underpinning the lifecycle verification above.

### Backups
- Default new backups to source-of-truth-only (exclude the derivable DuckDB/FAISS index); restoring a backup now automatically rebuilds the derived indexes.
- Add zstd compression (on by default) for plaintext backups; compression and AES-GCM encryption (`secure` extra) remain mutually exclusive.
- Add a `[backup]` retention policy (`keep_last`, `keep_monthly`, pinning) with restic-style independent-quota-then-union semantics; incremental-chain ancestors of any kept backup are pulled in transitively before pruning.
- Add a scheduled backup trigger that invokes the existing backup engine and skips no-op runs via change detection.
- Add selective DuckDB source-table export/import for smaller, source-only backup payloads.

### Deduplication
- Add cross-connector near-duplicate detection via embedding similarity, surfaced report-only in the disk dashboard; a structural mutation-guard test proves no merge/delete code path exists.
- Add a per-project retention policy schema (validated, fail-closed on malformed config) wired into the M8/M9 candidate-selection queries so lifecycle and distillation actions respect per-project thresholds and never-touch rules.

### Connectors
- Add an `omp` connector for oh-my-pi (OMP) sessions: session directory resolution, entry-point registration, and tool filtering/path detection.

### Web / UI
- Replace cached HTML serving with server-rendered Jinja2 templates, Alpine.js state bindings, and an esbuild + TypeScript toolchain.
- Add a fragment router with 20+ HTMX partial endpoints powering the new UI.
- Add a conversation management page with SSE-streamed rebuild progress, an expertise dashboard, a contradiction resolution UI, and the disk dashboard (cruft findings + duplicate suggestions).

### CLI
- Add root-level command aliases and a `searchat validate` release gate (`contracts`/`compatibility`/`performance smoke`/`packaging` groups) mirroring the CI build gate locally.

### Security
- Bind the web server to `127.0.0.1` (localhost only) by default, was `0.0.0.0` (all network interfaces). Set `SEARCHAT_HOST=0.0.0.0` explicitly to restore network-wide access, e.g. for a shared multi-user deployment.
- Reject any state-changing (non-GET/HEAD/OPTIONS) request whose browser-sent `Origin` header is neither same-origin nor in the configured CORS allowlist, closing a drive-by cross-origin request path against every state-changing endpoint.
- Reject a `backup_name` containing a path separator, `.`/`..`, or a colon in `BackupManager` and its API routes, closing a path-traversal issue that could read or write outside the backup directory.
- `GET /api/conversations/all` now defaults `limit` to 100 instead of returning every matching conversation (including full text) when the parameter is omitted.
- Escape `bookmark.title`/`bookmark.project_id` before rendering on the bookmarks page, closing a stored-XSS issue.
- Bump the `python-multipart` dependency floor past several denial-of-service CVEs in its form-parsing code.

## 0.6.0
### Search
- Replace BM25 (rank-bm25) keyword search with DuckDB FTS (full-text search with English stemmer)
- Add query synonym expansion (e.g., auth→authentication, db→database)
- Add optional cross-encoder re-ranking (`[reranking]` config section)
- Improve snippet generation for search results

### Chat
- Add session-based RAG chat with 30-minute TTL and 10-turn sliding window
- Return `X-Session-Id` header on streaming `/api/chat` responses
- Accept `session_id` field in chat request bodies

### New Features
- Add pattern mining endpoint (`POST /api/patterns/extract`)
- Add agent config generator (`POST /api/export/agent-config`) supporting claude.md, copilot-instructions.md, and cursorrules formats

### MCP
- Add `extract_patterns` tool for mining conversation patterns
- Add `generate_agent_config` tool for creating agent configuration files

### Data
- Add git context enrichment fields to Parquet schema (`files_mentioned`, `git_branch`)

### Security
- Restrict CORS to configurable origins (default: localhost only)
- Add `[server]` config section for CORS origin management

### Configuration
- Add `[reranking]` TOML section (enabled, model, top_k)
- Add `[server]` TOML section (cors_origins)

### Infrastructure
- Drop Python 3.9 support (minimum now Python 3.10)
- Remove `rank-bm25` dependency (replaced by DuckDB FTS)
- Add `patterns.py` router (14 routers total)
- Expand test suite to 840+ tests

## 0.5.0
- Backups: add incremental backups, backup-chain validation, and encrypted backups (AES-GCM) with secure extras.
- Search: add FAISS mmap option and temporal decay scoring.
- Export: add conversation downloads as TXT/HTML.
- Web/UI: add conversation viewer page; improve snapshot browsing and fix sidebar overflow/contrast.
- Connectors: improve Continue session indexing and metadata.
- Docs/Tools: add unified search architecture docs, benchmarking scripts, and refreshed infographics.

## 0.4.0
- Code search: index code blocks with extracted functions/classes/imports (tree-sitter when available), add `/api/search/code` symbol filters, and expose code-symbol endpoints.
- Embedded LLM: run chat/RAG locally via `searchat[embedded]` with model download + activation.
- Ghost mode: add `searchat-ghost` proactive history suggestions with desktop notifications.

## 0.3.0
- MCP: add `searchat-mcp` server for MCP clients (Claude Desktop, etc.).
- Connectors: add Cursor, Continue, and Aider connectors; expand tool filtering support.
- Docs: add MCP setup guide.

## 0.2.2
- Fix: add `eval_type_backport` for Python 3.9 so Pydantic/FastAPI can evaluate modern type syntax.

## 0.2.1
- Fix: make package importable on Python 3.9 by deferring annotation evaluation.

## 0.2.0
- Packaging: migrate build backend to hatchling; ship web assets + config templates.
- Connectors: add Codex and Gemini CLI connectors; enable entry-point discovery.
- CI: add build + install smoke tests.
- Web: `searchat-web` opens the default browser automatically on start.
