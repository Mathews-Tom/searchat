# API Reference

Base URL: `http://localhost:8000`

All API routes are prefixed with `/api` unless otherwise noted.

## Error Format

Errors are returned as:

```json
{"detail": "Error message"}
```

## Dataset Snapshots (Read-only Backups)

Many read endpoints accept an optional `snapshot` query parameter:

- `snapshot` (string): Backup directory name, e.g. `backup_YYYYMMDD_HHMMSS`

When `snapshot` is provided, the endpoint reads from the backup dataset without modifying the active index.

Notes:
- Snapshot mode is feature-flagged via `[snapshots] enabled`.
- Write-like operations are blocked in snapshot mode (typically `403`).
- If semantic components are not warmed up, some endpoints return `503` with a warming payload.

---

## Status

### GET /api/status

Server status and readiness information.

### GET /api/status/features

Feature flags and enabled/disabled capabilities.

---

## Search

### GET /api/search

Search conversations.

Parameters:
```
q                  string   Search query (required). Use "*" for keyword-only browsing.
mode               string   hybrid|semantic|keyword (default: hybrid)
project            string   Filter by project ID
tool               string   claude|vibe|opencode
date               string   today|week|month|custom
date_from           string   Custom date start (YYYY-MM-DD)
date_to             string   Custom date end (YYYY-MM-DD)
sort_by            string   relevance|date_newest|date_oldest|messages (default: relevance)
limit              int      1-100 (default: 20)
offset             int      0+ (default: 0)
highlight          bool     Enable highlight term extraction (default: false)
highlight_provider string   openai|ollama (required when highlight=true)
highlight_model    string   Optional model override
snapshot           string   Optional snapshot dataset (read-only)
```

Response:
```json
{
  "results": [
    {
      "conversation_id": "string",
      "project_id": "string",
      "title": "string",
      "created_at": "2026-01-31T07:04:00",
      "updated_at": "2026-01-31T07:04:00",
      "message_count": 42,
      "file_path": "/path/to/conversation.jsonl",
      "snippet": "string",
      "score": 0.95,
      "message_start_index": 0,
      "message_end_index": 12,
      "source": "local",
      "tool": "claude"
    }
  ],
  "total": 10,
  "search_time_ms": 45.2,
  "limit": 20,
  "offset": 0,
  "has_more": false,
  "highlight_terms": ["term1", "term2"]
}
```

Notes:
- If `mode=keyword`, search can succeed without semantic warmup.
- If semantic components are not ready, the endpoint returns `503` with a warming payload.

Examples:
```bash
# Hybrid search
curl "http://localhost:8000/api/search?q=authentication&mode=hybrid"

# Filter by tool + project
curl "http://localhost:8000/api/search?q=auth&tool=claude&project=myapp"

# Pagination
curl "http://localhost:8000/api/search?q=api&limit=20&offset=20"

# Snapshot search
curl "http://localhost:8000/api/search?q=auth&snapshot=backup_YYYYMMDD_HHMMSS"

# Highlight terms (LLM)
curl "http://localhost:8000/api/search?q=auth&highlight=true&highlight_provider=ollama"
```

---

### GET /api/search/suggestions

Autocomplete suggestions based on conversation titles.

Parameters:
```
q      string  Prefix (required)
limit  int     1-20 (default: 10)
```

---

### GET /api/projects

List projects in the index.

Parameters:
```
snapshot  string  Optional snapshot dataset (read-only)
```

Response:
```json
["project-a", "project-b"]
```

---

### GET /api/projects/summary

Project summaries (conversation/message counts).

Parameters:
```
snapshot  string  Optional snapshot dataset (read-only)
```

Response:
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

---

## Conversations

### GET /api/conversations/all

List conversations with optional filtering and pagination.

Parameters:
```
sort_by   string  length|date_newest|date_oldest|title (default: length)
project   string  Filter by project ID
tool      string  claude|vibe|opencode
date      string  today|week|month|custom
date_from  string  Custom date start (YYYY-MM-DD)
date_to    string  Custom date end (YYYY-MM-DD)
limit     int     1-5000 (optional)
offset    int     0+ (default: 0)
snapshot  string  Optional snapshot dataset (read-only)
```

Response:
```json
{
  "results": [
    {
      "conversation_id": "string",
      "project_id": "string",
      "title": "string",
      "created_at": "2026-01-31T07:04:00",
      "updated_at": "2026-01-31T07:04:00",
      "message_count": 42,
      "file_path": "/path/to/conversation.jsonl",
      "snippet": "string",
      "score": 0.0,
      "source": "local",
      "tool": "claude"
    }
  ],
  "total": 123,
  "search_time_ms": 12
}
```

---

### GET /api/conversation/{conversation_id}

Get a conversation and its messages.

Parameters:
```
snapshot  string  Optional snapshot dataset (read-only)
```

Response (shape):
```json
{
  "conversation_id": "string",
  "title": "string",
  "project_id": "string",
  "project_path": "/path/to/project",
  "file_path": "/path/to/conversation.jsonl",
  "message_count": 42,
  "tool": "claude",
  "messages": [
    {"role": "user", "content": "string", "timestamp": "2026-01-31T07:04:00"}
  ]
}
```

Notes:
- When reading the active dataset, if the source file is missing, the server may fall back to the indexed Parquet record.

---

### GET /api/conversation/{conversation_id}/code

Extract fenced code blocks from a conversation.

Parameters:
```
snapshot  string  Optional snapshot dataset (read-only)
```

Response (shape):
```json
{
  "conversation_id": "string",
  "title": "string",
  "total_blocks": 3,
  "code_blocks": [
    {
      "message_index": 0,
      "block_index": 0,
      "role": "assistant",
      "fence_language": "python",
      "language": "python",
      "language_source": "fence",
      "code": "print(123)",
      "timestamp": "2026-01-31T07:04:00",
      "lines": 1
    }
  ]
}
```

---

### GET /api/conversation/{conversation_id}/similar

Find similar conversations using FAISS embeddings.

Parameters:
```
limit     int     1-20 (default: 5)
snapshot  string  Optional snapshot dataset (read-only)
```

---

### GET /api/conversation/{conversation_id}/diff

Compute a line-oriented diff between conversations.

Parameters:
```
target_id     string  Optional explicit target conversation ID (defaults to top similar conversation)
source_start  int     Optional source message start index
source_end    int     Optional source message end index
snapshot      string  Optional snapshot dataset (read-only)
```

Response (shape):
```json
{
  "source_conversation_id": "abc",
  "target_conversation_id": "def",
  "summary": {"added": 10, "removed": 3, "unchanged": 120},
  "added": ["..."],
  "removed": ["..."],
  "unchanged": ["..."]
}
```

---

### GET /api/conversation/{conversation_id}/export

Export a conversation as a downloadable file.

Parameters:
```
format    string  json|markdown|text|ipynb|pdf (default: json)
snapshot  string  Optional snapshot dataset (read-only)
```

Notes:
- `ipynb` and `pdf` exports are feature-flagged. If disabled, the endpoint returns `404`.

---

### POST /api/conversations/bulk-export

Export multiple conversations as a ZIP archive.

Parameters:
```
snapshot  string  Optional snapshot dataset (read-only)
```

Request:
```json
{"conversation_ids": ["id1", "id2"], "format": "markdown"}
```

Notes:
- `conversation_ids` must be 1-100.
- `ipynb` and `pdf` exports are feature-flagged. If disabled, the endpoint returns `404`.

---

### POST /api/resume

Resume a conversation in a terminal (Claude/Vibe).

Request:
```json
{"conversation_id": "string"}
```

Response (shape):
```json
{
  "success": true,
  "tool": "claude",
  "cwd": "/path",
  "command": "claude resume ...",
  "platform": "windows|wsl|linux|macos"
}
```

---

### GET /conversation/{conversation_id}

Serve the web UI HTML (client-side routing handles the conversation view).

Response: HTML.

---

## Code

### POST /api/code/highlight

Server-side code highlighting using Pygments.

Request:
```json
{
  "blocks": [
    {"code": "print(123)", "language": "python", "language_source": "fence"},
    {"code": "SELECT 1", "language": null, "language_source": "detected"}
  ]
}
```

Response:
```json
{
  "results": [
    {"html": "<span class=...>", "used_language": "python", "guessed": false}
  ]
}
```

Errors:
- `500` if Pygments is not installed: `{"detail":"Pygments is required for code highlighting"}`

---

## Saved Queries

### GET /api/queries

List saved queries.

Response:
```json
{"total": 1, "queries": [{"id": "q_...", "name": "...", "query": "...", "filters": {}, "mode": "hybrid"}]}
```

---

### POST /api/queries

Create a saved query.

Request:
```json
{"name": "Auth", "description": "...", "query": "jwt refresh", "filters": {"project": "myapp"}, "mode": "hybrid"}
```

Response:
```json
{"success": true, "query": {"id": "q_..."}}
```

---

### PUT /api/queries/{query_id}

Update a saved query.

Request:
```json
{"name": "New name", "query": "...", "filters": {}, "mode": "keyword"}
```

---

### DELETE /api/queries/{query_id}

Delete a saved query.

---

### POST /api/queries/{query_id}/run

Record a query run / usage (used by the UI).

---

## Dashboards

Dashboards are feature-flagged via `[dashboards] enabled`.

### GET /api/dashboards

List dashboards.

Response:
```json
{"total": 1, "dashboards": [{"id": "d_...", "name": "...", "layout": {"widgets": [...]}}]}
```

---

### POST /api/dashboards

Create a dashboard.

Request (shape):
```json
{
  "name": "My dashboard",
  "description": "...",
  "layout": {"columns": 3, "widgets": [{"query_id": "q_...", "limit": 5}]},
  "refresh_interval": 60
}
```

---

### GET /api/dashboards/{dashboard_id}

Get a dashboard.

---

### PUT /api/dashboards/{dashboard_id}

Update a dashboard.

---

### DELETE /api/dashboards/{dashboard_id}

Delete a dashboard.

---

### GET /api/dashboards/{dashboard_id}/export

Download a dashboard definition as JSON (attachment).

---

### GET /api/dashboards/{dashboard_id}/render

Render a dashboard (executes saved queries for each widget).

Response (shape):
```json
{
  "dashboard": {"id": "d_...", "name": "..."},
  "widgets": [
    {
      "id": "w_...",
      "title": "...",
      "query_id": "q_...",
      "query": "...",
      "mode": "hybrid",
      "sort_by": "relevance",
      "results": [/* SearchResultResponse */],
      "total": 10,
      "search_time_ms": 12.3
    }
  ]
}
```

Notes:
- If any widget needs semantic search and the semantic components are not ready, this endpoint returns `503` with a warming payload.

---

## Chat

### POST /api/chat

Streaming chat endpoint.

Request (shape):
```json
{"query": "...", "model_provider": "ollama", "model_name": "ollama/gemma3", "session_id": "optional-session-id"}
```

Notes:
- Response includes `X-Session-Id` header for session tracking. Pass this value as `session_id` in subsequent requests to maintain conversation context.
- Sessions have a 30-minute TTL and maintain a 10-turn sliding window.
- In snapshot mode, chat endpoints are blocked (`403`).

---

### POST /api/chat-rag

Non-streaming RAG endpoint (structured response).

Request (shape):
```json
{"query": "...", "model_provider": "openai", "model_name": "gpt-4.1-mini", "session_id": "optional-session-id"}
```

Notes:
- Response includes `session_id` field.

---

## Patterns

### POST /api/patterns/extract

Extract recurring patterns from conversation archives using LLM analysis.

Request:
```json
{
  "topic": "authentication",
  "max_patterns": 10,
  "model_provider": "ollama",
  "model_name": "ollama/gemma3"
}
```

Parameters:
```
topic           string   Optional topic filter for pattern extraction
max_patterns    int      1-50 (default: 10)
model_provider  string   openai|ollama|embedded (default: ollama)
model_name      string   Optional model override
```

Response:
```json
{
  "patterns": [
    {
      "name": "Error-first validation",
      "description": "Functions validate inputs and return early on failure",
      "evidence": [
        {
          "conversation_id": "abc123",
          "date": "2026-02-10",
          "snippet": "Added validation checks at function entry..."
        }
      ],
      "confidence": 0.85
    }
  ],
  "total": 5
}
```

Notes:
- Requires semantic components to be ready (returns `503` if warming up).
- Uses hybrid search to find relevant conversations, then LLM to synthesize patterns.

---

## Docs

### POST /api/docs/summary

Generate a Markdown/AsciiDoc summary document by running multiple searches.

Feature flag:
- Requires `export.enable_tech_docs=true` (otherwise returns `404`).

Request:
```json
{
  "title": "Tech Docs Summary",
  "format": "markdown",
  "sections": [
    {
      "name": "Indexing",
      "query": "index_missing",
      "mode": "hybrid",
      "filters": {"project": "myapp", "tool": "claude", "date": "week"},
      "max_results": 10
    }
  ]
}
```

Response (shape):
```json
{
  "title": "Tech Docs Summary",
  "format": "markdown",
  "generated_at": "2026-01-31T07:04:00",
  "content": "# ...",
  "citation_count": 3,
  "citations": [{"conversation_id": "...", "title": "..."}]
}
```

---

### POST /api/export/agent-config

Generate agent configuration files from conversation patterns.

Request:
```json
{
  "format": "claude.md",
  "project_filter": "myapp",
  "model_provider": "ollama",
  "model_name": "ollama/gemma3"
}
```

Parameters:
```
format           string   claude.md|copilot-instructions.md|cursorrules (default: claude.md)
project_filter   string   Optional project to filter patterns
model_provider   string   openai|ollama|embedded (default: ollama)
model_name       string   Optional model override
```

Response:
```json
{
  "format": "claude.md",
  "content": "# myapp — CLAUDE.md\n\n## Conventions\n\n...",
  "pattern_count": 8,
  "project_filter": "myapp"
}
```

Notes:
- Extracts up to 15 patterns from conversation history.
- Formats patterns into the chosen agent config format.

---

## Statistics

### GET /api/statistics

Index statistics.

Parameters:
```
snapshot  string  Optional snapshot dataset (read-only)
```

---

## Analytics (Opt-in)

Analytics endpoints read from the active dataset only.

### GET /api/stats/analytics/summary

Parameters:
```
days  int  1-365 (default: 30)
```

### GET /api/stats/analytics/top-queries

Parameters:
```
limit  int  1-50 (default: 10)
days   int  1-365 (default: 30)
```

### GET /api/stats/analytics/dead-ends

### GET /api/stats/analytics/config

### GET /api/stats/analytics/trends

### GET /api/stats/analytics/heatmap

### GET /api/stats/analytics/agent-comparison

### GET /api/stats/analytics/topics

---

## Indexing

### POST /api/reindex

Blocked for data safety (`403`).

---

### POST /api/index_missing

Append-only indexing of new conversations.

---

## Backup

### POST /api/backup/create

Create a backup.

### GET /api/backup/list

List backups.

### POST /api/backup/restore

Restore from a backup.

### DELETE /api/backup/delete/{backup_name}

Delete a backup.

---

## Bookmarks

### GET /api/bookmarks

List bookmarks.

### POST /api/bookmarks

Create/update bookmark.

### GET /api/bookmarks/{conversation_id}

Get bookmark state.

### PATCH /api/bookmarks/{conversation_id}/notes

Update bookmark notes.

### DELETE /api/bookmarks/{conversation_id}

Remove bookmark.

---

## Admin

### GET /api/watcher/status

File watcher status.

### POST /api/shutdown

Graceful shutdown.

Parameters:
```
force  bool  Force shutdown even if indexing is in progress (default: false)
```
