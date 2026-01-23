# API Reference

Base URL: `http://localhost:8000`

## Search

### GET /api/search

Search conversations using hybrid, semantic, or keyword modes.

**Parameters:**
```
q          string   Search query (required)
mode       string   Search mode: hybrid|semantic|keyword (default: hybrid)
project    string   Filter by project ID
date       string   Filter: today|week|month|custom
date_start string   Custom date range start (ISO 8601)
date_end   string   Custom date range end (ISO 8601)
limit      int      Max results (1-100, default: 100)
sort_by    string   Sort: relevance|date_newest|date_oldest|messages
```

**Response:**
```json
{
  "results": [
    {
      "conversation_id": "string",
      "title": "string",
      "score": 0.95,
      "snippet": "string",
      "project_id": "string",
      "created_at": "2025-01-20T10:00:00",
      "message_count": 42,
      "file_path": "/path/to/conversation.jsonl"
    }
  ],
  "total_count": 10,
  "search_time_ms": 45.2,
  "mode_used": "hybrid"
}
```

**Search Modes:**
- `hybrid` - Combines BM25 keyword + FAISS semantic with RRF fusion (best for general queries)
- `semantic` - Meaning-based vector similarity (best for conceptual queries)
- `keyword` - Exact text matching (best for code, identifiers)

**Examples:**
```bash
# Hybrid search
curl "http://localhost:8000/api/search?q=authentication&mode=hybrid"

# Filter by project and date
curl "http://localhost:8000/api/search?q=bug+fix&project=myapp&date=week"

# Custom date range
curl "http://localhost:8000/api/search?q=refactor&date=custom&date_start=2025-01-01&date_end=2025-01-31"

# Sort by newest
curl "http://localhost:8000/api/search?q=api&sort_by=date_newest&limit=10"
```

---

### GET /api/projects

List all unique project IDs in the index.

**Response:**
```json
{
  "projects": ["project-a", "project-b", "project-c"]
}
```

**Caching:** Results cached for 5 minutes to improve performance.

---

## Conversations

### GET /api/conversations/all

List all conversations with optional filtering and sorting.

**Parameters:**
```
project    string   Filter by project ID
sort_by    string   Sort: date_newest|date_oldest|messages (default: date_newest)
limit      int      Max results (1-1000, default: 100)
```

**Response:**
```json
{
  "conversations": [
    {
      "conversation_id": "string",
      "title": "string",
      "project_id": "string",
      "created_at": "2025-01-20T10:00:00",
      "updated_at": "2025-01-20T15:30:00",
      "message_count": 42,
      "file_path": "/path/to/conversation.jsonl"
    }
  ],
  "total_count": 156
}
```

---

### GET /api/conversation/{conversation_id}

Get conversation metadata and messages.

**Response:**
```json
{
  "conversation_id": "string",
  "title": "string",
  "project_id": "string",
  "created_at": "2025-01-20T10:00:00",
  "updated_at": "2025-01-20T15:30:00",
  "message_count": 42,
  "file_path": "/path/to/conversation.jsonl",
  "messages": [
    {
      "type": "user|assistant",
      "content": "string",
      "timestamp": "2025-01-20T10:00:00"
    }
  ]
}
```

**Errors:**
- `404` - Conversation not found in index
- `404` - Conversation file not found on disk
- `500` - File parsing error

---

### POST /api/resume

Resume conversation in terminal (Claude Code or Mistral Vibe).

**Parameters:**
```
conversation_id   string   Conversation ID (required)
```

**Response:**
```json
{
  "success": true,
  "message": "Launching terminal session for conversation...",
  "conversation_id": "string",
  "platform": "windows|wsl|linux|macos",
  "agent": "claude|vibe"
}
```

**Behavior:**
- **Claude Code:** Launches terminal with `claude resume {conversation_id}`
- **Mistral Vibe:** Launches terminal in session directory
- **Platform Detection:** Auto-detects Windows/WSL/Linux/macOS
- **Terminal Selection:** Uses default terminal (PowerShell, Windows Terminal, gnome-terminal, etc.)

**Errors:**
- `404` - Conversation not found
- `500` - Terminal launch failed

---

### GET /conversation/{conversation_id}

Serve conversation as formatted HTML page.

**Response:** HTML page with conversation messages rendered.

---

## Statistics

### GET /api/statistics

Get index statistics and metadata.

**Response:**
```json
{
  "total_conversations": 1523,
  "total_messages": 45680,
  "avg_messages": 30.0,
  "total_projects": 42,
  "earliest_date": "2024-01-01T00:00:00",
  "latest_date": "2025-01-20T15:30:00"
}
```

---

## Indexing

### POST /api/reindex

Full reindex of all conversations.

**Response:**
```json
{
  "detail": "BLOCKED: Full reindex disabled for data safety..."
}
```

**Status:** `403 Forbidden`

**Note:** Blocked to prevent accidental data loss. Use `/api/index_missing` for safe append-only indexing.

---

### POST /api/index_missing

Index conversations not yet in the search index (append-only, safe).

**Response:**
```json
{
  "success": true,
  "new_conversations": 15,
  "total_files": 20,
  "already_indexed": 5,
  "time_seconds": 3.2,
  "message": "Indexed 15 new conversations in 3.2 seconds"
}
```

**Behavior:**
- Scans Claude Code and Mistral Vibe directories
- Skips files already in index (by file path)
- Appends new conversations to existing index
- Reloads SearchEngine after indexing
- Clears projects cache

**Response (no new files):**
```json
{
  "success": true,
  "new_conversations": 0,
  "total_files": 20,
  "already_indexed": 20,
  "message": "All 20 conversation files are already indexed"
}
```

**Errors:**
- `500` - Indexing failed (exception message in detail)

---

## Backup

### POST /api/backup/create

Create timestamped backup of index and config.

**Parameters:**
```
backup_name   string   Optional custom name (default: backup_YYYYMMDD_HHMMSS)
```

**Response:**
```json
{
  "success": true,
  "backup": {
    "backup_path": "/path/to/backups/backup_20250120_100000",
    "timestamp": "20250120_100000",
    "file_count": 5,
    "total_size_mb": 123.45
  },
  "message": "Backup created successfully at /path/to/backups/backup_20250120_100000"
}
```

**Backed Up:**
- `data/` - Parquet files, FAISS index, metadata
- `config/` - settings.toml, .env

**Errors:**
- `500` - Backup failed (disk full, permissions, etc.)

---

### GET /api/backup/list

List all available backups.

**Response:**
```json
{
  "backups": [
    {
      "backup_path": "/path/to/backups/backup_20250120_100000",
      "timestamp": "20250120_100000",
      "file_count": 5,
      "total_size_mb": 123.45
    }
  ],
  "total": 3,
  "backup_directory": "/path/to/backups"
}
```

**Errors:**
- `500` - Failed to list backups (permissions, disk error)

---

### POST /api/backup/restore

Restore from backup.

**Parameters:**
```
backup_name   string   Backup directory name (required)
```

**Response:**
```json
{
  "success": true,
  "restored_from": "backup_20250120_100000",
  "pre_restore_backup": {
    "backup_path": "/path/to/backups/pre_restore_20250120_101500",
    "timestamp": "20250120_101500",
    "file_count": 5,
    "total_size_mb": 125.30
  },
  "message": "Successfully restored from backup_20250120_100000"
}
```

**Behavior:**
- Creates pre-restore backup of current state
- Validates backup exists and contains data
- Restores data/ and config/ directories
- Reloads SearchEngine
- Clears projects cache

**Errors:**
- `404` - Backup not found
- `500` - Restore failed (corrupted backup, disk error)

---

### DELETE /api/backup/delete/{backup_name}

Delete a backup.

**Response:**
```json
{
  "success": true,
  "deleted": "backup_20250120_100000",
  "message": "Backup deleted successfully"
}
```

**Errors:**
- `404` - Backup not found
- `500` - Deletion failed (permissions, disk error)

---

## Admin

### GET /api/watcher/status

Get file watcher status.

**Response (running):**
```json
{
  "running": true,
  "watched_directories": [
    "/path/to/.claude/projects",
    "/path/to/.vibe/logs/session"
  ],
  "indexed_since_start": 15,
  "last_update": "2025-01-20T15:30:00"
}
```

**Response (not running):**
```json
{
  "running": false,
  "watched_directories": [],
  "indexed_since_start": 0,
  "last_update": null
}
```

---

### POST /api/shutdown

Gracefully shutdown server.

**Parameters:**
```
force   bool   Force shutdown even if indexing in progress (default: false)
```

**Response (graceful):**
```json
{
  "success": true,
  "forced": false,
  "message": "Server shutting down gracefully..."
}
```

**Response (blocked during indexing):**
```json
{
  "success": false,
  "indexing_in_progress": true,
  "operation": "manual_index",
  "files_total": 100,
  "message": "Cannot shutdown: indexing in progress. Use ?force=true to override."
}
```

**Response (forced):**
```json
{
  "success": true,
  "forced": true,
  "message": "Server shutdown (indexing interrupted)"
}
```

**Behavior:**
- Checks for ongoing indexing operations
- Stops file watcher
- Shuts down FastAPI server after 1 second delay
- `force=true` bypasses indexing check (may corrupt data)

---

## Error Responses

All endpoints return errors in this format:

```json
{
  "detail": "Error message description"
}
```

**Common Status Codes:**
- `400` - Bad Request (invalid parameters)
- `403` - Forbidden (blocked operation)
- `404` - Not Found (conversation, backup, etc.)
- `500` - Internal Server Error (indexing failed, disk error, etc.)

---

## CORS

CORS enabled for all origins to support Claude Code integration.

**Headers:**
```
Access-Control-Allow-Origin: *
Access-Control-Allow-Methods: GET, POST, DELETE
Access-Control-Allow-Headers: Content-Type
```

---

## Rate Limiting

None. API is local-only and assumes trusted environment.

---

## Authentication

None. API is local-only (localhost:8000) and assumes trusted environment.

---

## Performance

**Caching:**
- Projects list: 5 minute TTL
- Search results: Not cached (always fresh)

**Concurrency:**
- Indexing operations are serialized
- Multiple search requests can run in parallel

**Indexing State:**
Global state tracks ongoing indexing to prevent concurrent operations:
```json
{
  "in_progress": true,
  "operation": "manual_index|watcher_index",
  "started_at": "2025-01-20T15:30:00",
  "files_total": 100
}
```
