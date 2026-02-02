# Searchat Infographics

Interactive HTML visualizations of Searchat's architecture, data flows, and features.

## Available Infographics

### Core Features

#### [RAG Chat Pipeline](rag-chat-pipeline.html)
**Covers:** Query processing, hybrid search, context extraction, LLM integration, streaming responses
**Useful for:** Understanding how AI-powered Q&A works, configuring RAG parameters
**Updated:** v0.4.0 (2026-02-03)

#### [Backup & Restore Flow](backup-restore-flow.html)
**Covers:** Manual backups, automatic pre-restore backups, validation, atomic restore, snapshot mode
**Useful for:** Data safety procedures, troubleshooting restore issues, understanding validation gates
**Updated:** v0.4.0 (2026-02-03)

#### [File Watching & Live Indexing](file-watching-indexing.html)
**Covers:** FS event detection, debouncing, queue processing, append-only indexing, status tracking
**Useful for:** Understanding live indexing, configuring watcher settings, debugging event handling
**Updated:** v0.4.0 (2026-02-03)

### Architecture

#### [Multi-Agent Connector Architecture](multi-agent-connectors.html)
**Covers:** Connector protocol, registry pattern, 8 agent implementations, path resolution, format differences
**Useful for:** Adding new agent support, understanding extensibility, debugging connector issues
**Updated:** v0.4.0 (2026-02-03)

---

## Design System

All infographics follow a consistent design system:

- **Self-contained HTML**: No external dependencies, viewable offline
- **Color-coded tiers**: Blue (sources), Amber (processing), Green (storage), Purple (query), Rose (API), Teal (UI), Gold (watcher)
- **Interactive elements**: Hover states, semantic HTML, ARIA labels
- **Performance metrics**: Real benchmarks from production code
- **Technical precision**: Exact file paths, LOC counts, schema details

## Viewing Infographics

**In browser**: Open any `.html` file directly in Chrome, Firefox, or Safari
**From docs**: Follow links from `README.md` or `docs/architecture.md`

## Maintenance

When updating infographics:
1. Identify affected diagram(s)
2. Update inline HTML/CSS/SVG
3. Update version number and "Last updated" date
4. Add changelog entry in footer
5. Commit changes to git

**Update triggers**:
- Architecture changes
- Performance metric updates
- New feature additions
- Flow logic changes
