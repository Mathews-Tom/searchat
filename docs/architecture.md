# Searchat Architecture

## Visual Documentation

For interactive visual representations of Searchat's architecture:

- [Multi-Agent Connector Architecture](infographics/multi-agent-connectors.html) - Protocol-based extensibility for 8 AI agents
- [File Watching & Live Indexing](infographics/file-watching-indexing.html) - Event-driven real-time indexing system
- [RAG Chat Pipeline](infographics/rag-chat-pipeline.html) - Retrieval-Augmented Generation flow
- [Backup & Restore Flow](infographics/backup-restore-flow.html) - Data safety procedures

These diagrams show component relationships, data flows, and system interactions.

---

## Project Structure

```
searchat/                          # Project root
├── src/                          # All source code
│   └── searchat/                 # Main package
│       ├── __init__.py           # Package exports
│       ├── backup.py             # Backup/restore management
│       ├── platform_utils.py     # Platform detection and terminal launching
│       ├── query_parser.py       # Query parsing
│       │
│       ├── api/                  # FastAPI application layer
│       │   ├── __init__.py       # Router registry
│       │   ├── app.py            # FastAPI app factory
│       │   ├── dependencies.py   # Dependency injection
│       │   ├── models/           # Request/response models
│       │   │   ├── requests.py
│       │   │   └── responses.py
│       │   └── routers/          # API route modules
│       │       ├── search.py     # Search, projects
│       │       ├── conversations.py  # Conversation retrieval, resume
│       │       ├── indexing.py   # Reindex, index_missing
│       │       ├── backup.py     # Backup CRUD operations
│       │       ├── admin.py      # Shutdown, watcher status
│       │       ├── stats.py      # Index statistics
│       │       ├── status.py     # Server status and features
│       │       ├── chat.py       # RAG chat endpoints
│       │       ├── queries.py    # Saved queries CRUD
│       │       ├── code.py       # Code extraction and highlighting
│       │       ├── docs.py       # Tech docs + agent config
│       │       ├── patterns.py   # Pattern mining
│       │       ├── bookmarks.py  # Bookmark management
│       │       └── dashboards.py # Dashboard CRUD and rendering
│       │
│       ├── cli/                  # CLI interface
│       │   └── main.py           # SearchCLI class
│       │
│       ├── config/               # Configuration management
│       │   ├── settings.py       # Config class
│       │   ├── constants.py      # Global constants
│       │   └── path_resolver.py  # Path resolution logic
│       │
│       ├── core/                 # Business logic
│       │   ├── indexer.py        # Index building
│       │   ├── search_engine.py  # Search implementation
│       │   └── watcher.py        # File system watching
│       │
│       ├── services/             # Business services
│       │   ├── chat_service.py   # Session-based RAG pipeline
│       │   ├── pattern_mining.py # Pattern extraction from archives
│       │   ├── llm_service.py    # Multi-provider LLM interface
│       │   └── tech_docs_service.py # Tech docs generation
│       │
│       ├── models/               # Data models
│       │   ├── domain.py         # ConversationRecord, MessageRecord
│       │   ├── enums.py          # SearchMode, DateFilter
│       │   └── schemas.py        # PyArrow schemas
│       │
│       ├── setup/                # Setup wizard
│       │   └── wizard.py
│       │
│       └── web/                  # Frontend assets
│           ├── templates/
│           │   └── index.html    # Main HTML template
│           └── static/
│               ├── css/          # Modular stylesheets
│               │   ├── variables.css  # Theme colors
│               │   ├── base.css       # Base styles
│               │   ├── layout.css     # Grid layout
│               │   └── components.css # UI components
│               └── js/           # ES6 modules
│                   ├── main.js        # Entry point
│                   └── modules/
│                       ├── api.js          # API client
│                       ├── search.js       # Search UI
│                       ├── conversations.js # Conversation viewer
│                       ├── backup.js       # Backup UI
│                       ├── theme.js        # Theme management
│                       └── session.js      # State persistence
│
├── scripts/                      # Executable wrappers
│   ├── searchat                  # CLI wrapper
│   ├── searchat-web              # Web server wrapper
│   ├── setup-index               # Initial indexing
│   └── index-missing             # Append-only indexing
│
├── analysis/                     # Quality analysis tools
│   ├── README.md
│   ├── requirements.txt          # Separate dependencies
│   ├── scripts/                  # Analysis scripts
│   ├── data/                     # Sample data
│   └── output/                   # Analysis results
│
├── utils/                        # Utility scripts
│   └── vibe_converter.py         # Vibe history converter
│
├── tests/                        # Test suite
│   ├── conftest.py               # Pytest fixtures
│   ├── test_chunking.py          # Text chunking tests
│   ├── test_incremental.py       # Append-only indexing tests
│   ├── test_indexer.py           # Conversation processing tests
│   ├── test_query_parser.py      # Query parsing tests
│   ├── test_platform_utils.py    # Platform detection tests
│   ├── api/                      # API endpoint tests (120+ tests)
│   │   ├── test_search_routes.py
│   │   ├── test_conversations_routes.py
│   │   ├── test_chat_rag_routes.py
│   │   ├── test_patterns_routes.py
│   │   ├── test_agent_config.py
│   │   ├── test_stats_backup_routes.py
│   │   ├── test_indexing_admin_routes.py
│   │   ├── test_bookmarks_routes.py
│   │   ├── test_dashboards_routes.py
│   │   ├── test_analytics_routes.py
│   │   └── ...                   # 27 test files
│   └── unit/                     # Unit tests
│       ├── services/             # Service unit tests
│       ├── config/               # Config unit tests
│       ├── core/                 # Core logic tests
│       └── ...
│
├── config/                       # Config templates
│   ├── settings.default.toml
│   └── .env.example
│
├── docs/                         # Documentation
│   ├── architecture.md           # This file
│   ├── api-reference.md          # API endpoint documentation
│   └── terminal-launching.md     # Platform-specific terminal launching
│
├── pyproject.toml                # Modern Python packaging
├── pytest.ini                    # Pytest configuration
├── README.md
├── CONTRIBUTING.md
├── CLAUDE.md                     # Project-specific instructions
└── .gitignore
```

## Core Components

### 1. Indexer (`indexer.py`)

**Purpose:** Builds and manages the search index from conversation files.

**Key Classes:**
- `ConversationIndexer`: Main indexing logic
- `IndexStatistics`: Index metadata and stats

**Methods:**
- `index_all(force=False)`: Full rebuild (blocked if existing index)
- `index_append_only(file_paths)`: Safe append-only indexing
- `get_indexed_file_paths()`: Returns already indexed files
- `_process_conversation(file_path)`: Parse single conversation

**Data Flow:**
```
JSONL/JSON files
    ↓
_process_conversation()
    ↓
ConversationRecord
    ↓
Embeddings (sentence-transformers)
    ↓
Parquet (conversations) + FAISS (vectors)
```

### 2. Search Engine (`search_engine.py`)

**Purpose:** Executes hybrid search across conversations.

**Key Classes:**
- `SearchEngine`: Main search interface
- `SearchResult`: Individual result
- `SearchResults`: Result collection

**Search Modes:**
- **Hybrid**: DuckDB FTS + FAISS with Reciprocal Rank Fusion
- **Semantic**: FAISS vector similarity only
- **Keyword**: DuckDB FTS text search only

**Methods:**
- `search(query, mode="hybrid", filters=None)`: Execute search
- `get_conversation(conversation_id)`: Fetch full conversation
- `get_statistics()`: Index statistics

**Search Flow:**
```
User Query
    ↓
query_parser.parse() → structured query
    ↓
Synonym Expansion
    ↓
┌─────────────┬─────────────┐
│  DuckDB FTS │  FAISS      │
│  (keyword)  │  (semantic) │
└─────────────┴─────────────┘
    ↓           ↓
Reciprocal Rank Fusion (RRF)
    ↓
Optional: Cross-Encoder Re-ranking
    ↓
Ranked Results
```

### 3. Web API (`api/`)

**Purpose:** FastAPI server with modular routers and web UI.

**Structure:**
- `app.py` - FastAPI app factory, middleware, static file serving
- `dependencies.py` - Singleton instances (SearchEngine, BackupManager)
- `routers/` - 14 modular routers with 55+ endpoints
- `models/` - Pydantic request/response schemas

**Routers:**
- `search.py` - Search, list projects
- `conversations.py` - Conversation retrieval, session resume
- `stats.py` - Index statistics
- `backup.py` - Backup create/list/restore/delete
- `indexing.py` - Reindex (blocked), index_missing
- `admin.py` - Shutdown, watcher status
- `status.py` - Server status and feature flags
- `chat.py` - RAG chat (streaming and non-streaming)
- `queries.py` - Saved queries CRUD
- `code.py` - Code extraction and highlighting
- `docs.py` - Tech docs summaries and agent config export
- `patterns.py` - Pattern mining from archives
- `bookmarks.py` - Bookmark management
- `dashboards.py` - Dashboard CRUD and rendering

**See:** `docs/api-reference.md` for complete endpoint documentation

**Features:**
- Live file watching (watchdog)
- Debounced re-indexing (5min default)
- Safe shutdown (checks ongoing indexing)
- CORS restricted to configurable origins (default: localhost only)
- Modular ES6 frontend (CSS/JS separated)

### 4. Configuration (`config.py`)

**Purpose:** Load and manage configuration.

**Sources (priority order):**
1. Environment variables
2. `~/.searchat/config/settings.toml`
3. Default values

**Config Sections:**
- `paths`: Data directories
- `indexing`: Batch size, auto-index
- `search`: Default mode, result limits
- `embedding`: Model selection
- `performance`: Memory limits, caching
- `reranking`: Cross-encoder re-ranking settings
- `server`: CORS and server configuration

### 5. Path Resolver (`path_resolver.py`)

**Purpose:** Cross-platform path resolution.

**Features:**
- Platform detection (Windows, WSL, Linux, macOS)
- Claude directory discovery
- Vibe directory discovery
- Shared search directory resolution
- WSL/Windows path translation

### 6. Watcher (`watcher.py`)

**Purpose:** Monitor conversation directories for changes.

**Features:**
- Watchdog-based file system monitoring
- Debounced re-indexing (configurable)
- New file detection
- Modified file tracking
- Safe shutdown (waits for indexing)

## Data Storage

### Directory Layout

```
~/.searchat/
├── data/
│   ├── conversations/           # Parquet files
│   │   ├── shard_0.parquet
│   │   ├── shard_1.parquet
│   │   └── ...
│   └── indices/
│       ├── embeddings.faiss     # FAISS index
│       ├── embeddings.metadata.parquet
│       └── index_metadata.json
├── config/
│   ├── settings.toml            # User config
│   └── .env                     # Environment variables
└── logs/
    └── searchat.log             # Application logs
```

### Parquet Schema

**conversations/**
```
conversation_id: string
project_id: string (nullable)
file_path: string
title: string
created_at: timestamp
updated_at: timestamp
message_count: int64
messages: list[struct[...]]
full_text: string
embedding_id: int64
file_hash: string
indexed_at: timestamp
files_mentioned: list[string]
git_branch: string
tool: string
```

**embeddings.metadata.parquet**
```
embedding_id: int64
conversation_id: string
vector_index: int64
```

### FAISS Index

- **Type**: IndexFlatL2 (brute force, exact search)
- **Dimensions**: 384 (all-MiniLM-L6-v2)
- **Size**: ~1.5KB per conversation

## Search Algorithm

### Hybrid Search (RRF)

```python
def hybrid_search(query):
    # 1. Synonym expansion
    expanded_query = expand_synonyms(query)

    # 2. DuckDB FTS keyword search
    fts_results = duckdb_fts_search(expanded_query)
    fts_ranks = {doc_id: 1/(k+rank) for rank, doc_id in enumerate(fts_results)}

    # 3. FAISS semantic search
    query_embedding = embed(query)
    faiss_results = faiss.search(query_embedding)
    faiss_ranks = {doc_id: 1/(k+rank) for rank, doc_id in enumerate(faiss_results)}

    # 4. Reciprocal Rank Fusion
    all_docs = set(fts_ranks.keys()) | set(faiss_ranks.keys())
    rrf_scores = {
        doc_id: fts_ranks.get(doc_id, 0) + faiss_ranks.get(doc_id, 0)
        for doc_id in all_docs
    }

    # 5. Optional cross-encoder re-ranking
    if config.reranking.enabled:
        top_k = sorted(rrf_scores.items(), key=lambda x: -x[1])[:config.reranking.top_k]
        reranked = cross_encoder.rerank(query, top_k)
        return reranked

    # 6. Sort by fused score
    return sorted(rrf_scores.items(), key=lambda x: -x[1])
```

### Query Processing

```python
# Query parser supports:
query = "async +python -javascript \"exact phrase\""

parsed = {
    "terms": ["async"],
    "must_include": ["python"],
    "must_exclude": ["javascript"],
    "exact_phrases": ["exact phrase"]
}
```

## Performance Characteristics

### Indexing

| Operation | Speed |
|-----------|-------|
| Initial index | ~60s/100K conversations |
| Append-only add | ~0.1s/conversation (CPU), ~0.008s (GPU) |
| Embedding generation | Batched (32/batch) |

### Search

| Operation | Latency | Implementation |
|-----------|---------|----------------|
| Hybrid search | <100ms | DuckDB FTS + FAISS + RRF |
| Semantic search | <50ms | FAISS vector search |
| Keyword search | <30ms | DuckDB FTS |
| Filtered queries | <20ms | DuckDB predicate pushdown |

### Memory Usage

| Component | Size |
|-----------|------|
| Base | ~500MB |
| Embedding model | ~500MB |
| FAISS index | ~1.5KB per conversation |
| Parquet | ~50KB per 1K conversations |
| Filtered queries | Loads only matching rows (DuckDB predicate pushdown) |


## Extension Points

### Adding New Agent Support

1. Add parser in `indexer.py`:
```python
def _parse_new_agent_file(self, file_path: Path) -> ConversationRecord:
    # Parse custom format
    pass
```

2. Update `path_resolver.py`:
```python
@staticmethod
def resolve_new_agent_dirs():
    # Return list of directories
    pass
```

3. Add configuration in `constants.py`

### Custom Search Modes

Add to `search_engine.py`:
```python
def custom_search(self, query: str) -> SearchResults:
    # Custom search logic
    pass
```

### New API Endpoints

Add to `web_api.py`:
```python
@app.get("/api/custom")
async def custom_endpoint():
    # Custom API logic
    pass
```

## Testing

### Test Coverage

**Unit Tests (tests/):**
- `test_chunking.py` - Text chunking logic
- `test_incremental.py` - Append-only indexing
- `test_indexer.py` - Conversation processing
- `test_query_parser.py` - Query parsing
- `test_platform_utils.py` - Platform detection

**API Tests (tests/api/) - 120+ tests across 27 files:**
- `test_search_routes.py` (21 tests) - Search modes, filters, sorting
- `test_conversations_routes.py` (21 tests) - List, retrieve, resume
- `test_chat_rag_routes.py` - Chat and RAG endpoint tests
- `test_patterns_routes.py` - Pattern mining endpoint tests
- `test_agent_config.py` - Agent config generation tests
- `test_stats_backup_routes.py` (13 tests) - Statistics, backup operations
- `test_indexing_admin_routes.py` (8 tests) - Indexing, watcher, shutdown
- `test_bookmarks_routes.py` - Bookmark management tests
- `test_dashboards_routes.py` - Dashboard CRUD tests
- `test_analytics_routes.py` - Analytics endpoint tests
- And 17 more test files...

### Running Tests

```bash
pytest                          # Run all tests
pytest tests/api/              # Run API tests only
pytest -v                      # Verbose output
pytest -k test_search          # Run specific tests
pytest --cov=searchat          # Coverage report
pytest --cov-report=html       # HTML coverage report
```

## Security Considerations

1. **Local-only API**: No external network access
2. **No authentication**: Assumes trusted local environment
3. **File path validation**: Prevents directory traversal
4. **Safe indexing**: Append-only by default
5. **No code execution**: Only reads conversation data
