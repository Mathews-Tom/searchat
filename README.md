# Searchat

Semantic search and RAG-powered Q&A for AI coding agent conversations. Find past solutions by meaning, not just keywords, and ask questions about your conversation history.

**Fork of:** [Process-Point-Technologies-Corporation/searchat](https://github.com/Process-Point-Technologies-Corporation/searchat)

## Supported Agents

| Agent        | Location                                                     | Format   |
| ------------ | ------------------------------------------------------------ | -------- |
| Claude Code  | `~/.claude/projects/**/*.jsonl`                              | JSONL    |
| Mistral Vibe | `~/.vibe/logs/session/*.json`                                | JSON     |
| OpenCode     | `~/.local/share/opencode/storage/session/*/*.json`           | JSON     |
| OpenAI Codex | `~/.codex/sessions/**/rollout-*.jsonl`                       | JSONL    |
| Gemini CLI   | `~/.gemini/tmp/<project_hash>/chats/*.json`                  | JSON     |
| Continue     | `~/.continue/sessions/*.json`                                | JSON     |
| Cursor       | `.../Cursor/User/.../*.vscdb`                                | SQLite   |
| Aider        | `.aider.chat.history.md` (set `SEARCHAT_AIDER_PROJECT_DIRS`) | Markdown |

## Features

### Core Search

- **Hybrid Search** — BM25 keyword + FAISS semantic vectors with RRF fusion
- **Multi-Agent** — Search across Claude Code, Mistral Vibe, and OpenCode sessions
- **Tool Filters** — Filter results by specific agent (Claude, Vibe, or OpenCode)
- **Autocomplete** — Smart search suggestions as you type
- **Search History** — Persistent search history with LocalStorage

### AI-Powered Features

- **RAG Chat** — Ask questions about your conversation history with AI-powered answers
- **Embedded LLM** — Run RAG chat locally with a GGUF model (llama-cpp-python)
- **Semantic Highlights** — Optional LLM-generated highlight terms for search results
- **Conversation Similarity** — Discover related conversations using semantic similarity
- **Code Extraction** — Extract and view code snippets with syntax highlighting

### Organization & Management

- **Bookmarks** — Save and annotate favorite conversations
- **Saved Queries** — Save reusable searches (query + filters + mode)
- **Dashboards** — Build dashboards from saved queries (widgets + auto-refresh)
- **Search Analytics** — Track search patterns and usage statistics
- **Export** — Export conversations in JSON/Markdown/Text (optional PDF + Jupyter notebook)
- **Bulk Export** — Export multiple conversations at once
- **Pagination** — Navigate large result sets efficiently

### Data Safety & Performance

- **Live Indexing** — Auto-indexes new/modified files (5min debounce)
- **Append-Only** — Never deletes existing data, safe for long-term use
- **Backups** — Create and restore backups from UI or API
- **Snapshots** — Browse backups as read-only datasets ("snapshot" mode)
- **Safe Shutdown** — Detects ongoing indexing, prevents data corruption
- **DuckDB Storage** — Efficient Parquet-based storage with fast queries
- **FAISS Vectors** — High-performance semantic search

### User Experience

- **Keyboard Shortcuts** — Power user navigation and commands
- **Cross-Platform** — Windows, WSL, Linux, macOS
- **Local-First** — All data stays on your machine
- **Self-Search** — Agents can search their own history via API
- **MCP Server** — Let MCP clients (Claude Desktop, Cursor, etc.) query your local index
- **Terminal Resume** — Resume conversations directly in terminal

## Quick Start

### Install And Run (Standalone)

Install Searchat and build the initial index:

```bash
pip install searchat

# Optional: create ~/.searchat/config/settings.toml interactively
python -m searchat.setup

# Build the initial search index
searchat-setup-index

# Start the web server
searchat-web
```

Open http://localhost:8000

### Install From Source

```bash
git clone https://github.com/Mathews-Tom/searchat.git
cd searchat
pip install -e .

# First-time setup: build search index
python scripts/setup-index

# Start web server
searchat-web
```

Open http://localhost:8000

The setup script indexes all conversations from supported agents. On subsequent runs, the web server automatically indexes new conversations via live file watching.

## MCP Server (Claude Desktop, Cursor, ...)

```bash
pip install "searchat[mcp]"
searchat-mcp
```

See `docs/mcp-setup.md` for client configuration.

Available MCP tools:

- `search_conversations`
- `get_conversation`
- `find_similar_conversations`
- `ask_about_history`
- `list_projects`
- `get_statistics`

## Embedded LLM (Local GGUF)

Install the optional embedded dependency and download the default GGUF model:

```bash
pip install "searchat[embedded]"
searchat download-model --activate
```

When `llm.default_provider = "embedded"`, the server will auto-download the default model if `embedded_model_path` is not set.

## Enable Claude Self-Search

Add to `~/.claude/CLAUDE.md`:

````markdown
## Conversation History Search

Search past Claude Code conversations via local API (requires server running).

**Search:**

```bash
curl -s "http://localhost:8000/api/search?q=QUERY&limit=5" | jq '.results[] | {id: .conversation_id, title, snippet}'
```
````

**Get full conversation:**

```bash
curl -s "http://localhost:8000/api/conversation/CONVERSATION_ID" | jq '.messages[] | {role, content: .content[:500]}'
```

**Ask questions (RAG):**

```bash
curl -X POST "http://localhost:8000/api/chat" \
  -H "Content-Type: application/json" \
  -d '{"query": "How did we implement authentication?", "model_provider": "openai", "model_name": "gpt-4.1-mini"}'
```

**Ask questions (RAG, embedded/local):**

```bash
curl -X POST "http://localhost:8000/api/chat" \
  -H "Content-Type: application/json" \
  -d '{"query": "How did we implement authentication?", "model_provider": "embedded"}'
```

**When to use:**

- User asks "did we discuss X before" or "find that conversation about Y"
- Looking for previous solutions to similar problems
- Checking how something was implemented in past sessions
- Asking questions about past work (use RAG chat)

**Start server:** `searchat-web` from the searchat directory

````

See `CLAUDE.example.md` for the full template.

## Usage

### Web UI

```bash
searchat-web
````

Features:

- **Search Modes:** hybrid/semantic/keyword with autocomplete
- **Filters:** project, date range, tool (agent), similarity search
- **View Conversations:** Full message history with code extraction
- **Bookmarks:** Save and annotate favorite conversations
- **RAG Chat:** Ask questions about your conversation history
- **Analytics:** View search patterns and statistics
- **Saved Queries:** Save and re-run complex searches
- **Dashboards:** Create dashboards and widgets from saved queries
- **Export:** Download conversations in multiple formats
- **Backups:** Create and restore backups (left sidebar)
- **Snapshots:** Switch between active index and read-only backup snapshots
- **Keyboard Shortcuts:** Press `?` to see all shortcuts
- **Terminal Resume:** Resume conversations in terminal
- **Helpful Tips:** Search tips + API integration sidebars

### CLI

```bash
searchat  # interactive mode

# Download a default embedded GGUF model and update ~/.searchat/config/settings.toml
searchat download-model --activate

# Build the initial index (first-time setup)
searchat-setup-index
```

### API

#### Search & Discovery

```bash
# Search
curl "http://localhost:8000/api/search?q=authentication&mode=hybrid&limit=10"

# Search with tool filter (claude, vibe, opencode)
curl "http://localhost:8000/api/search?q=authentication&tool=claude&limit=10"

# Autocomplete suggestions
curl "http://localhost:8000/api/search/suggestions?q=auth&limit=5"

# Find similar conversations
curl "http://localhost:8000/api/conversation/{conversation_id}/similar?limit=5"

# Optional: request highlight terms for the UI (LLM)
curl "http://localhost:8000/api/search?q=auth&mode=hybrid&highlight=true&highlight_provider=ollama"

# Search with pagination
curl "http://localhost:8000/api/search?q=api&limit=20&offset=0"
```

#### Conversations

```bash
# Get conversation
curl "http://localhost:8000/api/conversation/{conversation_id}"

# List all conversations
curl "http://localhost:8000/api/conversations/all?limit=50"

# Extract code snippets
curl "http://localhost:8000/api/conversation/{conversation_id}/code"

# Code highlighting (Pygments)
curl -X POST "http://localhost:8000/api/code/highlight" \
  -H "Content-Type: application/json" \
  -d '{"blocks":[{"code":"print(123)","language":"python","language_source":"fence"}]}'

# Conversation diff
curl "http://localhost:8000/api/conversation/{conversation_id}/diff?target_id={other_conversation_id}"

# Export conversation
curl "http://localhost:8000/api/conversation/{conversation_id}/export?format=markdown"

# Bulk export
curl -X POST "http://localhost:8000/api/conversations/bulk-export" \
  -H "Content-Type: application/json" \
  -d '{"conversation_ids": ["id1", "id2"], "format": "json"}'

# Resume in terminal
curl -X POST "http://localhost:8000/api/resume?conversation_id={id}"
```

#### Bookmarks

```bash
# List bookmarks
curl "http://localhost:8000/api/bookmarks"

# Add bookmark
curl -X POST "http://localhost:8000/api/bookmarks" \
  -H "Content-Type: application/json" \
  -d '{"conversation_id": "abc123", "notes": "Important auth solution"}'

# Remove bookmark
curl -X DELETE "http://localhost:8000/api/bookmarks/{conversation_id}"
```

#### RAG Chat

```bash
# Ask question about conversation history
curl -X POST "http://localhost:8000/api/chat" \
  -H "Content-Type: application/json" \
  -d '{
    "query": "How did we implement authentication?",
    "model_provider": "openai",
    "model_name": "gpt-4.1-mini"
  }'

# Non-streaming RAG response with citations
curl -X POST "http://localhost:8000/api/chat-rag" \
  -H "Content-Type: application/json" \
  -d '{"query":"Summarize how backups work","model_provider":"ollama","model_name":"ollama/gemma3"}'

# Streaming response (default)
curl -X POST "http://localhost:8000/api/chat" \
  -H "Content-Type: application/json" \
  -d '{"query": "Explain the API design", "model_provider": "ollama", "model_name": "llama3"}' \
  --no-buffer
```

#### Analytics & Statistics

```bash
# Index statistics
curl "http://localhost:8000/api/statistics"

# Search analytics
curl "http://localhost:8000/api/stats/analytics/summary?days=7"

# Top queries / trends
curl "http://localhost:8000/api/stats/analytics/top-queries?limit=10&days=30"
curl "http://localhost:8000/api/stats/analytics/trends?days=30"

# List projects
curl "http://localhost:8000/api/projects"

# Project summary
curl "http://localhost:8000/api/projects/summary"
```

#### Saved Queries & Dashboards

```bash
# Saved queries
curl "http://localhost:8000/api/queries"

# Dashboards
curl "http://localhost:8000/api/dashboards"
```

#### Tech Docs (Optional)

Requires `export.enable_tech_docs=true`.

```bash
curl -X POST "http://localhost:8000/api/docs/summary" \
  -H "Content-Type: application/json" \
  -d '{
    "title": "Searchat Notes",
    "format": "markdown",
    "sections": [
      {"name": "Backups", "query": "backup restore", "mode": "hybrid", "filters": {"project": "myapp"}}
    ]
  }'
```

#### Snapshots (Read-only)

```bash
# Search within a backup snapshot
curl "http://localhost:8000/api/search?q=auth&snapshot=backup_YYYYMMDD_HHMMSS"
```

#### Indexing & Management

```bash
# Watcher status
curl "http://localhost:8000/api/watcher/status"

# Index missing conversations (append-only)
curl -X POST "http://localhost:8000/api/index_missing"

# Safe shutdown (checks for ongoing indexing)
curl -X POST "http://localhost:8000/api/shutdown"

# Force shutdown (override safety check)
curl -X POST "http://localhost:8000/api/shutdown?force=true"
```

#### Backups

```bash
# Create backup
curl -X POST "http://localhost:8000/api/backup/create"

# List backups
curl "http://localhost:8000/api/backup/list"

# Restore backup
curl -X POST "http://localhost:8000/api/backup/restore" \
  -H "Content-Type: application/json" \
  -d '{"name": "backup_YYYYMMDD_HHMMSS"}'

# Delete backup
curl -X DELETE "http://localhost:8000/api/backup/delete/backup_YYYYMMDD_HHMMSS"
```

### Utilities

```bash
# Add missing conversations to index
python scripts/index-missing

# Initial setup (interactive, safe options)
python scripts/setup-index

# Convert Vibe plaintext history to searchable sessions
python utils/vibe_converter.py
```

### As Library

```python
from searchat.core.search_engine import SearchEngine
from searchat.config.settings import Config

config = Config.load()
engine = SearchEngine(config.paths.search_directory, config)

results = engine.search("python async", mode="hybrid")
for r in results.results[:5]:
    print(f"{r.title}: {r.score:.3f}")
```

## Architecture

**Code Organization:**

- `src/searchat/api/` - FastAPI app with 13 modular routers (50+ endpoints)
- `src/searchat/core/` - Core indexing and search logic
- `src/searchat/services/` - Business services (chat, bookmarks, analytics, backup)
- `src/searchat/web/` - Modular frontend (HTML + CSS modules + ES6 JS)
- `tests/` - Comprehensive test suite (500+ tests)

**Data Flow:**

```plaintext
~/.claude/projects/**/*.jsonl     (source conversations)
~/.vibe/logs/session/*.json
~/.local/share/opencode/.../*.json
        │
        ▼ index_append_only()
        │
~/.searchat/data/
├── conversations/*.parquet       (DuckDB queryable)
└── indices/
    ├── embeddings.faiss          (semantic vectors)
    ├── embeddings.metadata.parquet
    └── index_metadata.json
```

**Search Flow:**

1. Query → BM25 keyword search + FAISS semantic search
2. Results merged via Reciprocal Rank Fusion
3. Hybrid ranking returns best of both approaches
4. Optional: Find similar conversations via vector similarity

**RAG Flow:**

1. User question → Search for relevant conversations
2. Top results used as context
3. LLM generates answer with conversation references
4. Streaming response to client

**Live Watching:**

- `watchdog` monitors conversation directories
- New files → indexed immediately
- Modified files → re-indexed after 5min debounce (configurable)
- `index_append_only()` adds to existing index
- Never deletes existing data

**Documentation:**

- `docs/features.md` - Complete feature list and descriptions
- `docs/architecture.md` - System design and components
- `docs/api-reference.md` - Complete API endpoint documentation
- `docs/terminal-launching.md` - Platform-specific terminal launching

## Configuration

Create `~/.searchat/config/settings.toml`:

```toml
[paths]
search_directory = "~/.searchat"
claude_directory_windows = "~/.claude/projects"
claude_directory_wsl = "//wsl$/Ubuntu/home/{username}/.claude/projects"

[indexing]
batch_size = 1000
auto_index = true
reindex_on_modification = true  # Re-index modified conversations
modification_debounce_minutes = 5  # Wait time before re-indexing
enable_connectors = true
enable_adaptive_indexing = true

[search]
default_mode = "hybrid"
max_results = 100
snippet_length = 200

[embedding]
model = "all-MiniLM-L6-v2"
batch_size = 32
device = "auto"  # auto|cuda|mps|cpu

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

[analytics]
enabled = false
retention_days = 30

[export]
enable_ipynb = false
enable_pdf = false
enable_tech_docs = false

[dashboards]
enabled = true

[snapshots]
enabled = true

[performance]
memory_limit_mb = 3000
query_cache_size = 100
```

Or use environment variables:

```bash
export SEARCHAT_DATA_DIR=~/.searchat
export SEARCHAT_PORT=8000
export SEARCHAT_EMBEDDING_MODEL=all-MiniLM-L6-v2
export SEARCHAT_REINDEX_ON_MODIFICATION=true
export SEARCHAT_MODIFICATION_DEBOUNCE_MINUTES=5
export SEARCHAT_OPENCODE_DATA_DIR=~/.local/share/opencode
export OPENAI_API_KEY=sk-...  # For RAG chat
export OLLAMA_BASE_URL=http://localhost:11434
```

## Requirements

- Python 3.9+
- ~2-3GB RAM (embeddings model + FAISS index)
- ~10MB disk per 1K conversations
- Optional: OpenAI API key or Ollama for RAG chat

### Dependencies

| Package               | Purpose                       |
| --------------------- | ----------------------------- |
| sentence-transformers | Embeddings (all-MiniLM-L6-v2) |
| faiss-cpu             | Vector similarity search      |
| pyarrow               | Parquet storage               |
| duckdb                | SQL queries on parquet        |
| fastapi + uvicorn     | Web API                       |
| watchdog              | File system monitoring        |
| litellm               | Multi-provider LLM interface  |
| rich                  | CLI formatting                |

## Safety

**Append-only indexing:** Never deletes existing data.

```python
indexer.index_append_only(file_paths)  # Safe: only adds new data
indexer.index_all()                     # Blocked if index exists
indexer.index_all(force=True)           # Explicit override required
```

**Safe shutdown:** Detects ongoing indexing operations.

```bash
# Check status, wait if indexing in progress
curl -X POST "http://localhost:8000/api/shutdown"

# Override safety check (may corrupt data)
curl -X POST "http://localhost:8000/api/shutdown?force=true"
```

**Backups:** Create backups before risky operations.

```bash
# Automatic pre-restore backup before any restore operation
curl -X POST "http://localhost:8000/api/backup/restore" -d '{"name": "backup_20260129_120000"}'
```

Protects against:

- Data loss from deleted/moved source files
- Corrupted Parquet/FAISS files during indexing
- Inconsistent metadata from interrupted operations

## Performance

| Metric            | Value                                              |
| ----------------- | -------------------------------------------------- |
| Search latency    | <100ms (hybrid), <50ms (semantic), <30ms (keyword) |
| Filtered queries  | <20ms (DuckDB predicate pushdown)                  |
| Index build       | ~60s per 100K conversations                        |
| Embedding         | Batched (CPU: 0.1s/conv, GPU: 0.008s/conv)         |
| Memory            | ~2-3GB                                             |
| Startup           | <3s                                                |
| RAG chat response | <2s (with OpenAI), <5s (with Ollama)               |
| Code extraction   | <50ms per conversation                             |
| Similarity search | <100ms (FAISS nearest neighbors)                   |

## Testing

```bash
pytest                          # Run the full test suite
pytest tests/api/              # Run API tests only
pytest -v                      # Verbose output
pytest -k test_search          # Run specific tests
pytest --cov=searchat          # Coverage report
pytest --cov-report=html       # HTML coverage report
```

**Test Coverage:**

- 500+ tests (API, UI contract tests, unit tests, perf gates)
- ~5,900 lines of test code
- Comprehensive coverage of all features
- API endpoint tests, unit tests, integration tests

## Troubleshooting

**Port in use:**

```bash
SEARCHAT_PORT=8001 searchat-web
```

**No conversations found:**

```bash
ls ~/.claude/projects/  # Verify conversations exist
```

**WSL not tracked:**
Configure `claude_directory_wsl` in `~/.searchat/config/settings.toml`:

```toml
claude_directory_wsl = "//wsl.localhost/Ubuntu/home/username/.claude/projects"
```

**Missing conversations after setup:**

```bash
python scripts/index-missing  # Index files not yet in search index
```

**Slow on WSL:**
Run from Windows Python or move repo to WSL filesystem (`~/projects/`).

**Import errors:**

```bash
pip install -e . --force-reinstall
```

**Empty environment variables override config:**
Remove empty values from `~/.searchat/config/.env` or set proper values.

**RAG chat not working:**

```bash
# For OpenAI
export OPENAI_API_KEY=sk-...

# For Ollama (local)
ollama serve  # Start Ollama server
export OLLAMA_BASE_URL=http://localhost:11434
```

## Fork Enhancements

This fork adds significant new features beyond the original:

- **RAG Chat** - AI-powered Q&A over conversation history
- **Bookmarks System** - Save and organize favorite conversations
- **Search Analytics** - Track and analyze search patterns
- **Conversation Similarity** - Discover related conversations
- **Code Extraction** - Extract code snippets with syntax highlighting
- **Saved Queries** - Reusable searches with stored filters
- **Dashboards** - Builder UI + widgets rendered from saved queries
- **Snapshots** - Browse backups as read-only datasets
- **Export Features** - JSON/Markdown/Text exports (optional PDF + Jupyter)
- **Bulk Export** - Export multiple conversations at once
- **Pagination** - Efficient navigation of large result sets
- **Autocomplete** - Smart search suggestions
- **Search History** - Persistent search history
- **Keyboard Shortcuts** - Power user shortcuts
- **OpenCode Support** - Added third agent support
- **Tool Filtering** - Filter by specific agent
- **Modern Typing** - Python 3.12 type hints throughout

See `docs/features.md` for complete feature documentation.

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

## License

MIT
