# Searchat Features

Complete feature documentation for Searchat - semantic search and RAG-powered Q&A for AI coding agent conversations.

## Table of Contents

- [Core Search Features](#core-search-features)
- [AI-Powered Features](#ai-powered-features)
- [Organization & Management](#organization--management)
- [Data Storage & Safety](#data-storage--safety)
- [User Experience](#user-experience)
- [Platform Support](#platform-support)
- [Performance & Optimization](#performance--optimization)
- [Developer Features](#developer-features)

---

## Core Search Features

### Hybrid Search

**Description:** Combines BM25 keyword matching with FAISS semantic vector search using Reciprocal Rank Fusion (RRF).

**How it works:**

1. Query processed by both BM25 (keyword) and FAISS (semantic) engines
2. Results from both approaches ranked independently
3. RRF algorithm merges rankings with configurable weight
4. Final results sorted by fused score

**Use cases:**

- General search where both keywords and meaning matter
- Finding conversations that use different terms for same concept
- Balancing precision (keyword) with recall (semantic)

**API:**

```bash
curl "http://localhost:8000/api/search?q=authentication&mode=hybrid&limit=10"
```

**Settings:**

```toml
[search]
default_mode = "hybrid"  # Use hybrid by default
```

---

### Semantic Search

**Description:** Pure vector similarity search using sentence embeddings (all-MiniLM-L6-v2) and FAISS index.

**How it works:**

1. Query converted to 384-dimensional embedding vector
2. FAISS searches for nearest neighbors in vector space
3. Cosine similarity used for ranking
4. Returns conceptually similar conversations

**Use cases:**

- Finding conversations about similar concepts with different wording
- Discovering related solutions you didn't know existed
- Exploring conversation themes

**API:**

```bash
curl "http://localhost:8000/api/search?q=async+programming&mode=semantic"
```

**Technical:**

- Model: all-MiniLM-L6-v2 (384 dimensions)
- Index: FAISS IndexFlatL2 (exact search)
- Memory: ~1.5KB per conversation
- Latency: <50ms

---

### Keyword Search

**Description:** Traditional BM25 text matching for exact term searches.

**How it works:**

1. Query tokenized into terms
2. BM25 algorithm scores documents by term frequency and rarity
3. Optimized for exact matches and code identifiers
4. Fast execution using DuckDB

**Use cases:**

- Finding specific function names, class names, error messages
- Code-specific searches (e.g., "IndexError", "async def")
- When you know exact terminology used

**API:**

```bash
curl "http://localhost:8000/api/search?q=IndexError&mode=keyword"
```

**Technical:**

- Algorithm: BM25 (Okapi BM25)
- Backend: DuckDB full-text search
- Latency: <30ms

---

### Tool Filtering

**Description:** Filter search results by specific AI agent (Claude Code, Mistral Vibe, or OpenCode).

**How it works:**

1. Metadata tracks which agent created each conversation
2. DuckDB predicate pushdown filters at query time
3. No index rebuild required
4. Fast filtered queries (<20ms)

**Use cases:**

- Search only Claude Code conversations
- Find solutions from specific agent
- Compare approaches across different agents

**API:**

```bash
# Filter by Claude Code
curl "http://localhost:8000/api/search?q=api+design&tool=claude"

# Filter by Mistral Vibe
curl "http://localhost:8000/api/search?q=refactoring&tool=vibe"

# Filter by OpenCode
curl "http://localhost:8000/api/search?q=testing&tool=opencode"
```

**Supported tools:**

- `claude` - Claude Code conversations
- `vibe` - Mistral Vibe sessions
- `opencode` - OpenCode sessions

---

### Autocomplete Suggestions

**Description:** Real-time search suggestions as you type, based on conversation content and search history.

**How it works:**

1. Prefix matching on conversation titles and common terms
2. Ranking by frequency and recency
3. Debounced API calls (300ms)
4. Caches results for performance

**Use cases:**

- Discover available topics quickly
- Avoid typos with suggested completions
- Learn what conversations exist

**API:**

```bash
curl "http://localhost:8000/api/search/suggestions?q=auth&limit=5"
```

**UI:** Built into web interface search bar

---

### Search History

**Description:** Persistent search history stored in browser LocalStorage.

**How it works:**

1. Each search query stored locally
2. Timestamp and result count tracked
3. Recent searches shown in dropdown
4. Clear history option available

**Use cases:**

- Repeat previous searches quickly
- Review search patterns
- Jump back to recent queries

**Storage:** Browser LocalStorage (client-side only)

**UI:**

- Click search box to see recent searches
- Click any recent search to re-execute
- Clear button to remove history

---

### Advanced Query Syntax

**Description:** Supports boolean operators and phrase matching for complex queries.

**Operators:**

- `+term` - Must include this term
- `-term` - Must exclude this term
- `"exact phrase"` - Match exact phrase
- `term1 term2` - Match either term (OR)

**Examples:**

```bash
# Must include "python", exclude "javascript"
curl "http://localhost:8000/api/search?q=+python -javascript"

# Exact phrase match
curl "http://localhost:8000/api/search?q=\"async await\""

# Combined
curl "http://localhost:8000/api/search?q=+python \"error handling\" -deprecated"
```

---

### Pagination

**Description:** Efficient pagination for large result sets.

**How it works:**

1. Server-side pagination with offset/limit
2. Configurable page size (default: 20)
3. Total count returned for UI
4. Cached results for fast page navigation

**Use cases:**

- Browse large result sets efficiently
- Reduce API response size
- Improve UI responsiveness

**API:**

```bash
# Get the second page (20 per page -> offset=20)
curl "http://localhost:8000/api/search?q=api&limit=20&offset=20"

# Custom page size
curl "http://localhost:8000/api/search?q=testing&limit=50&offset=0"
```

**Response:**

```json
{
  "results": [...],
  "total": 150,
  "limit": 20,
  "offset": 20,
  "has_more": true
}
```

---

## AI-Powered Features

### RAG Chat

**Description:** AI-powered question answering over your conversation history using Retrieval-Augmented Generation (RAG).

**How it works:**

1. User asks natural language question
2. System searches for relevant conversations (hybrid search)
3. Top conversations used as context for LLM
4. LLM generates answer with references
5. Streaming response returned to client

**Use cases:**

- "How did we implement authentication?"
- "What errors did we encounter with async code?"
- "Explain the API design decisions we made"
- "What solutions did we try for the database issue?"

**Supported LLM Providers:**

- **OpenAI** - GPT-4, GPT-3.5, etc. (requires API key)
- **Ollama** - Local models (Llama, Mistral, etc.)
- **Embedded (GGUF)** - Local GGUF models via llama-cpp-python

**API:**

```bash
# Streaming chat response
curl -X POST "http://localhost:8000/api/chat" \
  -H "Content-Type: application/json" \
  -d '{"query": "Explain how indexing works", "model_provider": "ollama", "model_name": "ollama/gemma3"}' \
  --no-buffer

# Streaming chat response (embedded/local)
curl -X POST "http://localhost:8000/api/chat" \
  -H "Content-Type: application/json" \
  -d '{"query": "Explain how indexing works", "model_provider": "embedded"}' \
  --no-buffer

# Non-streaming RAG response with citations
curl -X POST "http://localhost:8000/api/chat-rag" \
  -H "Content-Type: application/json" \
  -d '{"query": "How did we implement backups?", "model_provider": "openai", "model_name": "gpt-4.1-mini"}'
```

**Configuration:**

```toml
[llm]
default_provider = "ollama"
openai_model = "gpt-4.1-mini"
ollama_model = "ollama/gemma3"

# Embedded (local GGUF via llama-cpp-python)
embedded_model_path = ""
embedded_n_ctx = 4096
embedded_n_threads = 0
embedded_auto_download = true
embedded_default_preset = "qwen2.5-coder-1.5b-instruct-q4_k_m"

[chat]
enable_rag = true
enable_citations = true
```

**Setup (embedded/local GGUF):**

```bash
pip install -e ".[embedded]"
searchat download-model --activate
```

When `llm.default_provider = "embedded"` and `embedded_model_path` is not set, Searchat will auto-download the default preset and update `~/.searchat/config/settings.toml`.

**Environment:**

```bash
export OPENAI_API_KEY=sk-...
export OLLAMA_BASE_URL=http://localhost:11434
```

**Technical:**

- Retrieval: Hybrid search over indexed conversations
- Context selection: Top 6-16 chunks depending on query complexity
- Streaming: Chunked HTTP response (`/api/chat`)
- Readiness: Semantic search may return `503` until FAISS/embeddings are warmed up

**UI:** Chat panel in web interface with streaming responses

---

### Conversation Similarity

**Description:** Discover conversations similar to a given conversation using semantic vector similarity.

**How it works:**

1. Each conversation has pre-computed embedding vector
2. FAISS nearest neighbor search in vector space
3. Cosine similarity used for ranking
4. Returns top N most similar conversations

**Use cases:**

- Find related solutions after reading one conversation
- Discover follow-up conversations on same topic
- Explore conversation clusters
- Identify duplicate or repeated issues

**API:**

```bash
curl "http://localhost:8000/api/conversation/{conversation_id}/similar?limit=5"
```

**Response:**

```json
{
  "conversation_id": "abc123",
  "similar_conversations": [
    {
      "conversation_id": "def456",
      "title": "API error handling",
      "similarity_score": 0.92,
      "snippet": "We discussed error handling..."
    }
  ]
}
```

**Technical:**

- Algorithm: FAISS IndexFlatL2
- Metric: Cosine similarity
- Latency: <100ms
- Threshold: Configurable minimum similarity score

**UI:** "Similar Conversations" section in conversation viewer

---

### Code Extraction

**Description:** Automatically extract and highlight code snippets from conversations.

**How it works:**

1. Parses conversation messages for code blocks
2. Detects language from markdown fence tags
3. Applies syntax highlighting
4. Groups by language with tabs
5. One-click copy to clipboard

**Use cases:**

- Extract solutions quickly
- Copy code without formatting artifacts
- Review all code from a conversation
- Compare code across multiple conversations

**API:**

```bash
curl "http://localhost:8000/api/conversation/{conversation_id}/code"
```

**Response:**

```json
{
  "conversation_id": "abc123",
  "code_snippets": [
    {
      "language": "python",
      "code": "def authenticate(...):\n    ...",
      "line_number": 42,
      "message_index": 3
    }
  ],
  "total_snippets": 12,
  "languages": ["python", "javascript", "sql"]
}
```

**Supported languages:**

- Python, JavaScript, TypeScript, Java, C++, C#, Go, Rust
- SQL, HTML, CSS, Markdown, JSON, YAML
- Bash, PowerShell, Shell
- And 50+ more via Pygments

**UI:**

- Tabbed interface grouped by language
- Syntax highlighting via server-side Pygments (`/api/code/highlight`)
- Copy button for each snippet
- Line numbers for context

---

## Organization & Management

### Bookmarks

**Description:** Save and annotate favorite conversations for quick access.

**How it works:**

1. Bookmark conversations with optional notes
2. Stored persistently in JSON file
3. Enriched with conversation metadata
4. Searchable and filterable
5. Export/import support

**Use cases:**

- Mark important solutions
- Create reference library
- Track conversations to review later
- Annotate key insights

**API:**

```bash
# List bookmarks
curl "http://localhost:8000/api/bookmarks"

# Add bookmark
curl -X POST "http://localhost:8000/api/bookmarks" \
  -H "Content-Type: application/json" \
  -d '{
    "conversation_id": "abc123",
    "notes": "Great auth solution with JWT"
  }'

# Update notes
curl -X PATCH "http://localhost:8000/api/bookmarks/{conversation_id}" \
  -H "Content-Type: application/json" \
  -d '{"notes": "Updated notes"}'

# Remove bookmark
curl -X DELETE "http://localhost:8000/api/bookmarks/{conversation_id}"
```

**Storage:**

- Location: `~/.searchat/bookmarks.json`
- Format: JSON array
- Backup: Included in system backups

**UI:**

- Star icon to bookmark from search results
- Bookmarks sidebar panel
- Edit notes inline
- Filter search by bookmarked only

---

### Search Analytics

**Description:** Track and analyze search patterns, popular queries, and usage statistics.

**How it works:**

1. Every search logged with query, mode, timestamp
2. Statistics computed on-demand
3. Top queries identified by frequency
4. Query trends over time
5. Privacy-first: local-only storage

**Use cases:**

- Understand what you search for most
- Identify knowledge gaps
- Track research patterns
- Optimize indexing based on usage

**API:**

```bash
# Get analytics summary (opt-in)
curl "http://localhost:8000/api/stats/analytics/summary?days=7"

# Top queries
curl "http://localhost:8000/api/stats/analytics/top-queries?limit=10&days=30"

# Trends and heatmap
curl "http://localhost:8000/api/stats/analytics/trends?days=30"
curl "http://localhost:8000/api/stats/analytics/heatmap?days=30"

# Per-agent comparison and topic clusters
curl "http://localhost:8000/api/stats/analytics/agent-comparison?days=30"
curl "http://localhost:8000/api/stats/analytics/topics?days=30&k=8"
```

**Metrics tracked:**

- Total searches
- Unique queries
- Average results per query
- Search modes used
- Query frequency
- Zero-result queries

**Configuration:**

```toml
[analytics]
enabled = false
retention_days = 30
```

**Storage:** DuckDB database in `~/.searchat/analytics/analytics.duckdb`

**UI:** Analytics dashboard with charts and insights

---

### Saved Queries

**Description:** Save frequently-used searches (query + filters + mode) and re-run them from the UI.

**API:**

```bash
# List saved queries
curl "http://localhost:8000/api/queries"

# Create saved query
curl -X POST "http://localhost:8000/api/queries" \
  -H "Content-Type: application/json" \
  -d '{"name":"Auth investigations","query":"jwt refresh","mode":"hybrid","filters":{"project":"myapp","tool":"claude"}}'
```

**Storage:** `~/.searchat/saved_queries.json`

**UI:** Saved Queries panel in the left sidebar.

---

### Dashboards

**Description:** Build dashboards from saved queries and render them as widgets (with optional auto-refresh).

**API:**

```bash
# List dashboards
curl "http://localhost:8000/api/dashboards"

# Render a dashboard (executes the saved queries in its widgets)
curl "http://localhost:8000/api/dashboards/{dashboard_id}/render"
```

**Storage:** `~/.searchat/dashboards.json`

**Configuration:**

```toml
[dashboards]
enabled = true
```

**UI:** Dashboards view + dashboard builder editor.

---

### Tech Docs Summary (Optional)

**Description:** Generate a single Markdown/AsciiDoc document by running multiple searches and stitching the results into named sections.

**API:**

```bash
curl -X POST "http://localhost:8000/api/docs/summary" \
  -H "Content-Type: application/json" \
  -d '{
    "title": "Tech Notes",
    "format": "markdown",
    "sections": [
      {"name": "Indexing", "query": "index_missing", "mode": "hybrid", "max_results": 10}
    ]
  }'
```

**Configuration:**

```toml
[export]
enable_tech_docs = false
```

---

### Export Conversations

**Description:** Export conversations in multiple formats for external use.

**Supported formats:**

- **JSON** - Structured data with full metadata
- **Markdown** - Formatted text with code blocks
- **Text** - Plain text, minimal formatting
- **Jupyter Notebook** (`ipynb`) - Optional (feature-flagged)
- **PDF** - Optional (feature-flagged)

**How it works:**

1. Conversation loaded from Parquet storage
2. Messages formatted for target format
3. Metadata included (title, date, participants)
4. Code blocks preserved with syntax
5. File generated and streamed to client

**Use cases:**

- Share conversations with team
- Archive important solutions
- Create documentation from conversations
- Print for offline reference
- Import into other tools

**API:**

```bash
# Export as Markdown
curl "http://localhost:8000/api/conversation/{conversation_id}/export?format=markdown" \
  -o conversation.md

# Export as JSON
curl "http://localhost:8000/api/conversation/{conversation_id}/export?format=json" \
  -o conversation.json

# Export as PDF
curl "http://localhost:8000/api/conversation/{conversation_id}/export?format=pdf" \
  -o conversation.pdf
```

**Configuration:**

```toml
[export]
enable_ipynb = false
enable_pdf = false
enable_tech_docs = false
```

**UI:**

- Export button in conversation viewer
- Format dropdown selector
- Download progress indicator

---

### Bulk Export

**Description:** Export multiple conversations at once in a single operation.

**How it works:**

1. Select multiple conversations by ID
2. Choose export format
3. Server creates ZIP archive with all conversations
4. Single download contains all files
5. Maintains folder structure and naming

**Use cases:**

- Backup entire projects
- Share multiple solutions
- Archive by date range
- Bulk documentation generation

**API:**

```bash
curl -X POST "http://localhost:8000/api/conversations/bulk-export" \
  -H "Content-Type: application/json" \
  -d '{
    "conversation_ids": ["abc123", "def456", "ghi789"],
    "format": "markdown"
  }' \
  --output conversations.zip
```

**Response:** ZIP file containing all exported conversations

**UI:**

- Checkbox selection in search results
- "Export Selected" button
- Progress bar for bulk operations

---

### Project Management

**Description:** Organize conversations by project for easy filtering and navigation.

**How it works:**

1. Project ID extracted from conversation file path
2. Projects indexed automatically
3. List projects via API
4. Filter searches by project
5. Statistics per project

**Use cases:**

- Focus on specific project
- Compare solutions across projects
- Project-specific analytics
- Team collaboration boundaries

**API:**

```bash
# List all projects
curl "http://localhost:8000/api/projects"

# Search within project
curl "http://localhost:8000/api/search?q=api&project=myapp"

# Project summary (conversation/message counts per project)
curl "http://localhost:8000/api/projects/summary"
```

**Response:**

```json
[
  {
    "project_id": "myapp",
    "conversation_count": 150,
    "message_count": 4500,
    "updated_at": "2026-01-31T07:04:00"
  }
]
```

**UI:**

- Project dropdown filter
- Project badges on results
- Project statistics in sidebar

---

## Data Storage & Safety

### Append-Only Indexing

**Description:** Safe indexing that only adds new conversations, never deletes existing data.

**How it works:**

1. Checks if conversation already indexed (by file path hash)
2. Only processes new or modified conversations
3. Preserves all existing Parquet shards
4. Atomic operations prevent corruption
5. Never deletes indexed conversations

**Safety guarantees:**

- No data loss from deleted source files
- Orphaned conversations remain searchable
- Index can only grow (unless explicit force)
- Failed indexing doesn't corrupt existing data

**API:**

```bash
# Safe append-only indexing
curl -X POST "http://localhost:8000/api/index_missing"
```

**Code:**

```python
# Safe method
indexer.index_append_only(file_paths)  # Only adds new

# Unsafe (blocked by default)
indexer.index_all()  # Raises error if index exists
indexer.index_all(force=True)  # Requires explicit override
```

**Protection:**

- `index_all()` blocked if existing index detected
- Dangerous `index_incremental()` method removed
- Reindex API endpoint returns 403 Forbidden

---

### Backups

**Description:** Create and restore backups of the entire search index and configuration.

**What's backed up:**

- Parquet conversation data
- FAISS vector index
- Index metadata
- Configuration files
- Bookmarks
- Analytics database

**How it works:**

1. Creates timestamped backup directory
2. Copies all data files
3. Generates backup metadata JSON
4. Validates backup integrity
5. Supports restore with pre-restore backup

**Use cases:**

- Before major version upgrades
- Regular scheduled backups
- Before risky operations
- Disaster recovery

**API:**

```bash
# Create backup
curl -X POST "http://localhost:8000/api/backup/create"

# List backups
curl "http://localhost:8000/api/backup/list"

# Restore (creates pre-restore backup)
curl -X POST "http://localhost:8000/api/backup/restore" \
  -d '{"name": "backup_20260129_120000"}'

# Delete backup
curl -X DELETE "http://localhost:8000/api/backup/delete/backup_20260129_120000"
```

**Storage:**

- Location: `~/.searchat/backups/`
- Format: `backup_YYYYMMDD_HHMMSS/`
- Retention: Manual deletion only
- Compression: Optional (not yet implemented)

**Safety:**

- Automatic pre-restore backup before restore
- Backup validation before restore
- Atomic restore operation
- Rollback on failure

**UI:**

- Backup manager in left sidebar
- One-click create backup
- List with size and date
- Restore confirmation dialog

---

### Read-only Index Snapshots

**Description:** Browse/search a backup as a read-only dataset ("snapshot") without overwriting your active index.

**How it works:**

- Select a backup by name with `snapshot=<backup_dir_name>` on supported endpoints.
- When snapshot mode is active, write-like operations are blocked (403).

**API:**

```bash
# Search within a backup snapshot
curl "http://localhost:8000/api/search?q=authentication&snapshot=backup_YYYYMMDD_HHMMSS"

# Read a conversation from a snapshot
curl "http://localhost:8000/api/conversation/{conversation_id}?snapshot=backup_YYYYMMDD_HHMMSS"
```

**Configuration:**

```toml
[snapshots]
enabled = true
```

**UI:** Dataset selector in the left sidebar + a read-only banner when a snapshot is selected.

---

### Live File Watching

**Description:** Automatically detect and index new or modified conversation files in real-time.

**How it works:**

1. `watchdog` library monitors conversation directories
2. File system events trigger indexing
3. Debounce period prevents re-indexing in-progress files
4. New files indexed immediately
5. Modified files re-indexed after delay

**Configuration:**

```toml
[indexing]
auto_index = true
reindex_on_modification = true
modification_debounce_minutes = 5  # Wait 5 minutes before re-indexing
```

**Watched directories:**

- `~/.claude/projects/**/*.jsonl`
- `~/.vibe/logs/session/*.json`
- `~/.local/share/opencode/storage/session/*/*.json`

**API:**

```bash
# Get watcher status
curl "http://localhost:8000/api/watcher/status"
```

**Response:**

```json
{
  "running": true,
  "watched_directories": [
    "/home/user/.claude/projects",
    "/home/user/.vibe/logs/session"
  ],
  "indexed_since_start": 15,
  "last_update": "2024-12-31T15:30:00"
}
```

**Performance:**

- Low overhead (<1% CPU)
- Efficient debouncing
- Background indexing
- No UI blocking

---

### Safe Shutdown

**Description:** Graceful server shutdown that detects ongoing indexing and prevents corruption.

**How it works:**

1. Shutdown request checks for active indexing
2. If indexing in progress, shutdown blocked
3. User notified with status information
4. Force option available to override (dangerous)
5. Watcher stopped before shutdown

**Use cases:**

- Safe server restart
- System shutdown
- Docker container stop
- Prevent data corruption

**API:**

```bash
# Safe shutdown (waits for indexing)
curl -X POST "http://localhost:8000/api/shutdown"

# Force shutdown (may corrupt data)
curl -X POST "http://localhost:8000/api/shutdown?force=true"
```

**Response (blocked):**

```json
{
  "success": false,
  "indexing_in_progress": true,
  "operation": "manual_index",
  "files_total": 100,
  "message": "Cannot shutdown: indexing in progress. Use ?force=true to override."
}
```

**Response (success):**

```json
{
  "success": true,
  "forced": false,
  "message": "Server shutting down gracefully..."
}
```

**UI:** Stop button with status indicator

---

### DuckDB Storage

**Description:** Efficient Parquet-based storage with SQL query capabilities via DuckDB.

**How it works:**

1. Conversations stored as Parquet files
2. DuckDB provides SQL interface
3. Predicate pushdown for fast filters
4. Columnar storage for compression
5. Schema evolution supported

**Advantages:**

- **Fast queries**: <20ms for filtered queries
- **Low memory**: Only loads required columns/rows
- **Compression**: ~50KB per 1K conversations
- **SQL interface**: Familiar query syntax
- **Versioning**: Schema evolution with backward compatibility

**Schema:**

```python
conversation_id: string
project_id: string (nullable)
file_path: string
title: string
created_at: timestamp
updated_at: timestamp
message_count: int64
messages: list[struct[type, content, timestamp]]
full_text: string
embedding_id: int64
file_hash: string
indexed_at: timestamp
tool: string  # claude, vibe, opencode
```

**Storage:**

- Location: `~/.searchat/data/conversations/*.parquet`
- Sharding: Multiple files for performance
- Format: Apache Parquet
- Compression: Snappy

---

### FAISS Vector Index

**Description:** High-performance semantic vector search using Facebook AI Similarity Search (FAISS).

**How it works:**

1. Each conversation embedded to 384-dim vector
2. Vectors stored in FAISS IndexFlatL2
3. Exact nearest neighbor search
4. Cosine similarity metric
5. Fast in-memory index

**Technical specs:**

- Index type: IndexFlatL2 (exact search)
- Dimensions: 384 (all-MiniLM-L6-v2)
- Memory: ~1.5KB per conversation
- Latency: <50ms for semantic search
- Capacity: Millions of conversations

**Storage:**

- Location: `~/.searchat/data/indices/embeddings.faiss`
- Format: FAISS binary format
- Metadata: `embeddings.metadata.parquet`

**Advantages:**

- Exact search (no approximation)
- Memory-mapped for large indices
- Optimized BLAS operations
- Parallel query processing

---

## User Experience

### Keyboard Shortcuts

**Description:** Power user shortcuts for efficient navigation and search.

**Available shortcuts:**

| Shortcut            | Action                       |
| ------------------- | ---------------------------- |
| `/` or `Ctrl/Cmd+K` | Focus search box             |
| `Enter`             | Execute search               |
| `Esc`               | Clear search / close modals  |
| `Ctrl/Cmd+B`        | Toggle bookmarks panel       |
| `Ctrl/Cmd+H`        | Toggle search history        |
| `Ctrl/Cmd+E`        | Export current conversation  |
| `Ctrl/Cmd+S`        | Save bookmark                |
| `Ctrl/Cmd+R`        | Resume in terminal           |
| `↑/↓`               | Navigate results             |
| `Enter` (on result) | Open conversation            |
| `?`                 | Show keyboard shortcuts help |

**UI:**

- Press `?` to show shortcuts overlay
- Visual hints for discoverability
- Configurable in settings (future)

---

### Responsive Design

**Description:** Fully responsive web interface that works on desktop, tablet, and mobile.

**Breakpoints:**

- Desktop: ≥1200px
- Laptop: 1024-1199px
- Tablet: 768-1023px
- Mobile: <768px

**Adaptations:**

- Sidebar collapses on mobile
- Touch-friendly buttons
- Swipe gestures for navigation
- Optimized layouts per screen size

---

### Dark Mode

**Description:** System-aware dark mode with manual toggle.

**How it works:**

1. Detects system preference via CSS media query
2. Loads appropriate theme
3. Manual toggle available
4. Preference saved to LocalStorage
5. Smooth transitions between themes

**CSS:**

```css
@media (prefers-color-scheme: dark) {
  /* Dark mode styles */
}
```

**UI:** Theme toggle button in header

---

### Real-Time Updates

**Description:** Live updates as new conversations are indexed.

**How it works:**

1. Server-Sent Events (SSE) connection
2. Server pushes updates on new conversations
3. UI updates search results automatically
4. Statistics refresh in real-time
5. Notification badges for new content

**Use cases:**

- See new conversations as they're created
- Real-time collaboration awareness
- Live statistics dashboard

---

### Terminal Resume

**Description:** Open conversations directly in terminal for continuation.

**How it works:**

1. Detects platform (Windows, WSL, Linux, macOS)
2. Launches platform-appropriate terminal
3. Executes agent-specific resume command
4. Continues conversation from last message

**Supported:**

- **Claude Code**: `claude resume {conversation_id}`
- **Mistral Vibe**: Opens session directory
- **OpenCode**: Session-specific command (if supported)

**Platforms:**

- Windows: PowerShell, Windows Terminal
- WSL: wsl.exe with terminal
- Linux: gnome-terminal, xterm
- macOS: Terminal.app, iTerm2

**API:**

```bash
curl -X POST "http://localhost:8000/api/resume?conversation_id={id}"
```

**UI:** "Resume in Terminal" button on conversation viewer

---

## Platform Support

### Cross-Platform Compatibility

**Supported platforms:**

- Windows 10/11
- Windows Subsystem for Linux (WSL 1/2)
- Linux (Ubuntu, Debian, Fedora, Arch, etc.)
- macOS (10.15+)

**Path resolution:**

- Automatic platform detection
- WSL/Windows path translation
- Symlink resolution
- Unicode path support

---

### Multi-Agent Support

**Supported AI agents:**

1. **Claude Code**
   - Location: `~/.claude/projects/**/*.jsonl`
   - Format: JSONL (one message per line)
   - Metadata: project_id, conversation_id
   - Resume: `claude resume {id}`

2. **Mistral Vibe**
   - Location: `~/.vibe/logs/session/*.json`
   - Format: JSON session files
   - Metadata: session_id, timestamps
   - Resume: Opens session directory

3. **OpenCode**
   - Location: `~/.local/share/opencode/storage/session/*/*.json`
   - Format: JSON conversation files
   - Metadata: session_id, project context
   - Resume: Session-specific command

**Adding new agents:**
See `docs/architecture.md` for extension guide.

---

## Performance & Optimization

### Query Performance

| Operation         | Latency   | Notes                     |
| ----------------- | --------- | ------------------------- |
| Hybrid search     | <100ms    | BM25 + FAISS + RRF        |
| Semantic search   | <50ms     | FAISS only                |
| Keyword search    | <30ms     | BM25 only                 |
| Filtered queries  | <20ms     | DuckDB predicate pushdown |
| Autocomplete      | <10ms     | Cached prefix matching    |
| Conversation load | <50ms     | Single Parquet row        |
| Code extraction   | <50ms     | Regex + syntax detection  |
| Similarity search | <100ms    | FAISS k-NN                |
| RAG chat          | 1-5s      | LLM latency               |
| Export            | 100-500ms | Format conversion         |

---

### Memory Usage

| Component       | Memory      | Notes                |
| --------------- | ----------- | -------------------- |
| Base            | ~500MB      | Python + libraries   |
| Embedding model | ~500MB      | all-MiniLM-L6-v2     |
| FAISS index     | ~1.5KB/conv | 384-dim vectors      |
| DuckDB          | ~200MB      | Query buffers        |
| Parquet cache   | ~100MB      | Recent conversations |
| Total           | ~2-3GB      | Typical workload     |

---

### Indexing Performance

| Metric          | Speed             | Notes                 |
| --------------- | ----------------- | --------------------- |
| Initial index   | ~60s/100K conv    | Full build            |
| Append-only     | 0.1s/conv (CPU)   | Add new conversation  |
| Append-only     | 0.008s/conv (GPU) | With GPU acceleration |
| Embedding batch | 32 conv/batch     | Optimized batch size  |
| Parquet write   | 1000 conv/s       | Bulk write            |
| FAISS add       | 10000 vec/s       | Vector insertion      |

---

### Caching Strategy

**Query cache:**

- Size: 100 queries (configurable)
- TTL: 5 minutes
- Eviction: LRU

**Project list cache:**

- TTL: 5 minutes
- Invalidation: On index update

**Autocomplete cache:**

- TTL: 1 hour
- Prefix-based caching

---

### Startup Optimization

**Lazy loading:**

- Embedding model loaded on first search
- FAISS index memory-mapped
- DuckDB on-demand connection
- Configuration cached

**Startup sequence:**

1. Load configuration (<100ms)
2. Initialize FastAPI app (<500ms)
3. Start file watcher (<100ms)
4. Load index metadata (<500ms)
5. Ready to serve (<2s total)

**First search:**

- Load embedding model (+2-3s)
- Load FAISS index (memory-mapped)
- Warm up DuckDB connection
- Cache results

---

## Developer Features

### MCP Server (Optional)

Searchat ships an MCP server so MCP clients can query your local index.

**Install:**

```bash
pip install "searchat[mcp]"
```

**Run:**

```bash
searchat-mcp
```

**Tools:** `search_conversations`, `get_conversation`, `find_similar_conversations`, `ask_about_history`, `list_projects`, `get_statistics`

See `docs/mcp-setup.md` for configuration.

### REST API

**13 routers, 50+ endpoints:**

- Search & filtering
- Conversation CRUD
- Bookmarks management
- Analytics & statistics
- Indexing operations
- Backup & restore
- Admin & monitoring
- RAG chat
- Export functionality
- Saved queries
- Dashboards
- Code highlighting
- Tech docs summaries

See `docs/api-reference.md` for complete documentation.

---

### Python Library

Use Searchat as a Python library:

```python
from searchat.core.search_engine import SearchEngine
from searchat.config.settings import Config

config = Config.load()
engine = SearchEngine(config.paths.search_directory, config)

# Search
results = engine.search("async programming", mode="hybrid")
for r in results.results[:5]:
    print(f"{r.title}: {r.score:.3f}")

# Get conversation
conv = engine.get_conversation("abc123")
print(f"{conv.title}: {len(conv.messages)} messages")

# Similar conversations
similar = engine.find_similar("abc123", limit=5)
for s in similar:
    print(f"{s.title}: {s.similarity_score:.2f}")
```

---

### CLI Interface

Terminal-friendly interface:

```bash
# Interactive mode
searchat

# Download a default embedded GGUF model and update config
searchat download-model --activate

# Build the initial search index (first-time setup)
searchat-setup-index
```

---

### Webhooks (Future)

**Planned features:**

- On new conversation indexed
- On search query
- On bookmark created
- On backup created

**Use cases:**

- Integration with Slack, Discord
- Analytics pipeline
- Custom notifications
- External backups

---

### Plugin System (Future)

**Planned features:**

- Custom search modes
- Custom export formats
- Custom analytics
- Agent plugins

**Extension points:**

- Search algorithm plugins
- Storage backend plugins
- LLM provider plugins
- UI theme plugins

---

## Summary

Searchat provides comprehensive search, AI-powered Q&A, and organization features for AI coding agent conversations:

- **3 search modes** - Hybrid, semantic, keyword
- **3 AI agents** - Claude Code, Mistral Vibe, OpenCode
- **50+ API endpoints** - Full REST API
- **500+ tests** - Extensive API/UI/unit/perf coverage
- **RAG chat** - Ask questions about conversation history
- **Bookmarks** - Organize favorites
- **Export** - Multiple formats
- **Analytics** - Track usage patterns
- **Saved queries** - Reusable searches
- **Dashboards** - Widgets built from saved queries
- **Snapshots** - Read-only browsing of backups
- **Safe & fast** - Append-only, <100ms queries
- **Cross-platform** - Windows, WSL, Linux, macOS

## Standalone Installation

Install Searchat as an application and run it locally:

```bash
pip install searchat

# Optional: interactive config wizard (writes ~/.searchat/config/settings.toml)
python -m searchat.setup

# Build the initial search index
searchat-setup-index

# Run the web UI
searchat-web
```

For more information:

- [API Reference](api-reference.md)
- [Architecture](architecture.md)
- [Terminal Launching](terminal-launching.md)
- [Contributing](../CONTRIBUTING.md)
