# Changelog

All notable changes to this project will be documented in this file.

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
