# Changelog

All notable changes to this project will be documented in this file.

## Unreleased

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
