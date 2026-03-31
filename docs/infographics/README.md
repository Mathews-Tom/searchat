# Searchat Infographics

Architecture and feature visuals for Searchat, spanning Markdown + Mermaid system diagrams and self-contained HTML walkthroughs.

## Quick Links

- **PyPI Package**: [https://pypi.org/project/searchat/](https://pypi.org/project/searchat/)
- **Installation**: `pip install searchat` (from PyPI) or `pip install -e .` (from source)
- **Documentation**: [Main README](../../README.md) | [Architecture](../architecture.md) | [API Reference](../api-reference.md)
- **Source Code**: [GitHub Repository](https://github.com/Mathews-Tom/searchat)

## Available Infographics

### System Overview

#### [Current Architecture Overview](../architecture.md)
**Covers:** Connector ingestion, watcher/indexer flow, DuckDB storage, unified retrieval, expertise, knowledge graph, palace, API/MCP/CLI/UI surfaces
**Useful for:** Understanding the live system topology and how the major subsystems fit together today
**Format:** Markdown + Mermaid
**Updated:** 2026-04-01

### Core Features

#### [RAG Chat Pipeline](rag-chat-pipeline.html)
**Covers:** Query processing, hybrid search, context extraction, LLM integration, streaming responses
**Useful for:** Understanding how AI-powered Q&A works, configuring RAG parameters
**Updated:** v0.6.0 (2026-02-17)

#### [Backup & Restore Flow](backup-restore-flow.html)
**Covers:** Manual backups, automatic pre-restore backups, validation, atomic restore, snapshot mode
**Useful for:** Data safety procedures, troubleshooting restore issues, understanding validation gates
**Updated:** v0.6.0 (2026-02-17)

#### [File Watching & Live Indexing](file-watching-indexing.html)
**Covers:** FS event detection, debouncing, queue processing, append-only indexing, status tracking
**Useful for:** Understanding live indexing, configuring watcher settings, debugging event handling
**Updated:** v0.6.0 (2026-02-17)

### Architecture

#### [Multi-Agent Connector Architecture](multi-agent-connectors.html)
**Covers:** Connector protocol, registry pattern, 8 agent implementations, path resolution, format differences
**Useful for:** Adding new agent support, understanding extensibility, debugging connector issues
**Updated:** v0.6.0 (2026-02-17)

---

## Design System

The repository uses two documentation formats:

- **Markdown + Mermaid**: Canonical system-level architecture and code-aligned diagrams
- **Self-contained HTML**: Feature-specific visual walkthroughs, viewable offline
- **Color-coded tiers**: Blue (sources), Amber (processing), Green (storage), Purple (query), Rose (API), Teal (UI), Gold (watcher)
- **Interactive elements**: Hover states, semantic HTML, ARIA labels
- **Performance metrics**: Real benchmarks from production code
- **Technical precision**: Exact file paths, LOC counts, schema details

## Viewing Infographics

**In browser**: Open any `.html` file directly in Chrome, Firefox, or Safari
**In Markdown renderers**: View `docs/architecture.md` anywhere Mermaid diagrams are supported
**From docs**: Follow links from `README.md` or `docs/architecture.md`

## Maintenance

When updating infographics:
1. Identify affected diagram(s)
2. Update Mermaid or inline HTML/CSS/SVG, depending on the artifact
3. Update version number and "Last updated" date
4. Add changelog entry in footer
5. Commit changes to git

**Update triggers**:
- Architecture changes
- Performance metric updates
- New feature additions
- Flow logic changes
