#!/usr/bin/env python
"""FastAPI backend for Searchat"""

import os
import warnings
from pathlib import Path
from typing import Any
from datetime import datetime, timedelta
import json

from fastapi import FastAPI, HTTPException, Query, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, FileResponse
from pydantic import BaseModel
import signal
import sys

from searchat.core import SearchEngine, ConversationIndexer, ConversationWatcher
from searchat.models import SearchMode, SearchFilters, SearchResult
from searchat.config import Config, PathResolver
from searchat.services import PlatformManager, BackupManager
from searchat.api import dependencies as deps
from searchat.config.constants import (
    DEFAULT_HOST,
    DEFAULT_PORT,
    PORT_SCAN_RANGE,
    ENV_PORT,
    ENV_HOST,
    ERROR_INVALID_PORT,
    ERROR_PORT_IN_USE,
)

warnings.filterwarnings(
    "ignore",
    message=r"resource_tracker: There appear to be .* leaked semaphore objects to clean up at shutdown",
    category=UserWarning,
)


# Data models
class SearchRequest(BaseModel):
    query: str
    mode: str = "hybrid"
    project: str | None = None
    date_filter: str | None = None


class SearchResultResponse(BaseModel):
    conversation_id: str
    project_id: str
    title: str
    created_at: str
    updated_at: str
    message_count: int
    file_path: str
    snippet: str
    score: float
    message_start_index: int | None = None
    message_end_index: int | None = None
    source: str  # WIN or WSL
    tool: str


class ConversationMessage(BaseModel):
    role: str
    content: str
    timestamp: str


class ConversationResponse(BaseModel):
    conversation_id: str
    title: str
    project_id: str
    project_path: str | None = None
    file_path: str
    message_count: int
    tool: str
    messages: list[ConversationMessage]


class ResumeRequest(BaseModel):
    conversation_id: str


# Initialize FastAPI
app = FastAPI(title="Searchat API")

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize search engine
config = Config.load()
search_dir = PathResolver.get_shared_search_dir(config)
search_engine = SearchEngine(search_dir, config)
indexer = ConversationIndexer(search_dir, config)
platform_manager = PlatformManager()

# Initialize backup manager
backup_manager = BackupManager(search_dir)

# Cache for projects list
projects_cache = None

# Watcher state
watcher: ConversationWatcher | None = None
watcher_stats = {"indexed_count": 0, "last_update": None}

# Indexing state tracking
indexing_state = {
    "in_progress": False,
    "operation": None,  # "manual_index" or "watcher"
    "started_at": None,
    "files_total": 0,
    "files_processed": 0
}


def on_new_conversations(file_paths: list[str]) -> None:
    """Callback when watcher detects new conversation files."""
    global projects_cache, watcher_stats, indexing_state
    import logging

    logger = logging.getLogger(__name__)
    logger.info(f"Indexing {len(file_paths)} new conversations...")

    try:
        # Mark indexing in progress
        indexing_state["in_progress"] = True
        indexing_state["operation"] = "watcher"
        indexing_state["started_at"] = datetime.now().isoformat()
        indexing_state["files_total"] = len(file_paths)
        indexing_state["files_processed"] = 0

        stats = indexer.index_append_only(file_paths)

        if stats.new_conversations > 0:
            # Reload search engine to pick up new data
            search_engine.refresh_index()
            projects_cache = None  # Clear cache

            watcher_stats["indexed_count"] += stats.new_conversations
            watcher_stats["last_update"] = datetime.now().isoformat()

            logger.info(
                f"Indexed {stats.new_conversations} new conversations "
                f"in {stats.update_time_seconds:.2f}s"
            )
    except Exception as e:
        logger.error(f"Failed to index new conversations: {e}")
    finally:
        # Mark indexing complete
        indexing_state["in_progress"] = False
        indexing_state["operation"] = None


def _extract_vibe_messages(data: dict) -> list[ConversationMessage]:
    messages: list[ConversationMessage] = []
    for entry in data.get('messages', []):
        role = entry.get('role')
        if role not in ('user', 'assistant'):
            continue
        content = entry.get('content') or entry.get('text') or ''
        if not isinstance(content, str) or not content.strip():
            continue
        timestamp = entry.get('timestamp', '')
        messages.append(ConversationMessage(
            role=role,
            content=content,
            timestamp=timestamp,
        ))
    return messages


def _resolve_opencode_data_root(session_file_path: str) -> Path:
    session_path = Path(session_file_path)
    if "storage" in session_path.parts:
        storage_index = session_path.parts.index("storage")
        return Path(*session_path.parts[:storage_index])
    if len(session_path.parents) >= 4:
        return session_path.parents[3]
    return session_path.parent


def _load_opencode_parts_text(data_root: Path, message_id: str) -> str:
    parts_dir = data_root / "storage" / "part" / message_id
    if not parts_dir.exists():
        return ""

    parts: list[str] = []
    for part_file in sorted(parts_dir.glob("*.json")):
        try:
            content = part_file.read_text(encoding="utf-8")
            part = json.loads(content)
        except (json.JSONDecodeError, UnicodeDecodeError, OSError):
            continue

        text = part.get("text")
        if isinstance(text, str) and text.strip():
            parts.append(text.strip())
            continue

        state = part.get("state")
        if isinstance(state, dict):
            output = state.get("output")
            if isinstance(output, str) and output.strip():
                parts.append(output.strip())

    return "\n\n".join(parts)


def _extract_opencode_message_text(data_root: Path, message: dict) -> str:
    def _normalize_text(value: object) -> str:
        if isinstance(value, str) and value.strip():
            return value.strip()
        if isinstance(value, dict):
            text = value.get("text") or value.get("content") or value.get("value")
            if isinstance(text, str) and text.strip():
                return text.strip()
        if isinstance(value, list):
            parts = []
            for block in value:
                if not isinstance(block, dict):
                    continue
                text = block.get("text") or block.get("content") or block.get("value")
                if isinstance(text, str) and text.strip():
                    parts.append(text.strip())
            if parts:
                return "\n\n".join(parts)
        return ""

    content_text = _normalize_text(message.get("content"))
    if content_text:
        return content_text

    text_text = _normalize_text(message.get("text"))
    if text_text:
        return text_text

    message_text = _normalize_text(message.get("message"))
    if message_text:
        return message_text

    message_id = message.get("id")
    if isinstance(message_id, str):
        parts_text = _load_opencode_parts_text(data_root, message_id)
        if parts_text:
            return parts_text

    summary = message.get("summary")
    if isinstance(summary, dict):
        body = summary.get("body")
        if isinstance(body, str) and body.strip():
            return body.strip()

        title = summary.get("title")
        if isinstance(title, str) and title.strip():
            return title.strip()

    return ""


def _load_opencode_messages(session_file_path: str, session_id: str) -> list[ConversationMessage]:
    data_root = _resolve_opencode_data_root(session_file_path)
    candidate_roots = [data_root]
    for opencode_dir in PathResolver.resolve_opencode_dirs(config):
        if opencode_dir not in candidate_roots:
            candidate_roots.append(opencode_dir)

    raw_messages: list[tuple[float | None, str, str, str]] = []
    for root in candidate_roots:
        messages_dir = root / "storage" / "message" / session_id
        if not messages_dir.exists():
            continue

        for message_file in messages_dir.glob("*.json"):
            try:
                content = message_file.read_text(encoding="utf-8")
                message = json.loads(content)
            except (json.JSONDecodeError, UnicodeDecodeError, OSError):
                continue

            role = message.get("role") or message.get("type")
            if role not in ("user", "assistant"):
                continue

            text = _extract_opencode_message_text(root, message)
            if not text:
                continue

            created = message.get("time", {}).get("created")
            created_ts = None
            if isinstance(created, (int, float)):
                created_ts = created / 1000
            raw_messages.append((created_ts, message_file.name, text, role))

        if raw_messages:
            break

    if not raw_messages:
        try:
            session_content = Path(session_file_path).read_text(encoding="utf-8")
            session_data = json.loads(session_content)
        except (json.JSONDecodeError, UnicodeDecodeError, OSError):
            session_data = None

        if isinstance(session_data, dict):
            session_messages = session_data.get("messages")
            if isinstance(session_messages, list):
                for index, entry in enumerate(session_messages):
                    if not isinstance(entry, dict):
                        continue
                    role = entry.get("role") or entry.get("type")
                    if role not in ("user", "assistant"):
                        continue
                    text = _extract_opencode_message_text(data_root, entry)
                    if not text:
                        continue
                    created = entry.get("time", {}).get("created")
                    created_ts = None
                    if isinstance(created, (int, float)):
                        created_ts = created / 1000
                    raw_messages.append((created_ts, f"{index:06d}", text, role))

    raw_messages.sort(key=lambda item: (item[0] or 0.0, item[1]))

    messages: list[ConversationMessage] = []
    for created_ts, _name, text, role in raw_messages:
        timestamp = ""
        if created_ts is not None:
            timestamp = datetime.fromtimestamp(created_ts).isoformat()
        messages.append(ConversationMessage(
            role=role,
            content=text,
            timestamp=timestamp,
        ))

    return messages


def _load_opencode_project_path(session_file_path: str) -> str | None:
    session_path = Path(session_file_path)
    try:
        content = session_path.read_text(encoding="utf-8")
        data = json.loads(content)
    except (json.JSONDecodeError, UnicodeDecodeError, OSError):
        return None

    project_id = data.get("projectID")
    if not isinstance(project_id, str):
        return None

    data_root = _resolve_opencode_data_root(session_file_path)
    project_file = data_root / "storage" / "project" / f"{project_id}.json"
    if not project_file.exists():
        return None

    try:
        project_content = project_file.read_text(encoding="utf-8")
        project_data = json.loads(project_content)
    except (json.JSONDecodeError, UnicodeDecodeError, OSError):
        return None

    worktree = project_data.get("worktree")
    if isinstance(worktree, str) and worktree.strip():
        return worktree
    return None


def _load_vibe_project_path(session_file_path: str) -> str | None:
    session_path = Path(session_file_path)
    try:
        content = session_path.read_text(encoding="utf-8")
        data = json.loads(content)
    except (json.JSONDecodeError, UnicodeDecodeError, OSError):
        return None

    working_dir = data.get('metadata', {}).get('environment', {}).get('working_directory')
    if isinstance(working_dir, str) and working_dir.strip():
        return working_dir
    return None


@app.on_event("startup")
async def startup_event():
    """Start the file watcher on server startup."""
    global watcher
    import logging

    logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger(__name__)

    watcher = ConversationWatcher(
        config=config,
        on_update=on_new_conversations,
        batch_delay_seconds=5.0,
        debounce_seconds=2.0,
    )

    # Initialize with already-indexed files
    indexed_paths = indexer.get_indexed_file_paths()
    watcher.set_indexed_files(indexed_paths)

    watcher.start()
    logger.info(f"Live watcher started, monitoring {len(watcher.get_watched_directories())} directories")


@app.on_event("shutdown")
async def shutdown_event():
    """Stop the file watcher on server shutdown."""
    global watcher
    if watcher:
        watcher.stop()
        watcher = None


@app.get("/api/watcher/status")
async def get_watcher_status():
    """Get live watcher status."""
    return {
        "running": watcher.is_running if watcher else False,
        "watched_directories": [str(d) for d in watcher.get_watched_directories()] if watcher else [],
        "indexed_since_start": watcher_stats["indexed_count"],
        "last_update": watcher_stats["last_update"],
    }


@app.get("/")
async def root():
    """Serve the main HTML page"""
    html_path = Path(__file__).parent.parent / "web" / "index.html"
    if html_path.exists():
        return FileResponse(html_path)
    else:
        return HTMLResponse("""
<!DOCTYPE html>
<html>
<head>
    <title>Searchat</title>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">

    <!-- Preload fonts for optimal performance -->
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link rel="preload" as="style" href="https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@400;500;700&family=IBM+Plex+Sans:wght@400;500;600&family=JetBrains+Mono:wght@400;500&display=swap">
    <link href="https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@400;500;700&family=IBM+Plex+Sans:wght@400;500;600&family=JetBrains+Mono:wght@400;500&display=swap" rel="stylesheet">

    <style>
        /* CSS Variables - Light Theme (GitHub Light) */
        :root {
            --bg-primary: #ffffff;
            --bg-surface: #f6f8fa;
            --bg-elevated: #ffffff;
            --text-primary: #24292f;
            --text-muted: #57606a;
            --text-subtle: #6e7781;
            --border-default: #d0d7de;
            --border-muted: #d8dee4;
            --accent-primary: #0969da;
            --accent-secondary: #0550ae;
            --success: #1a7f37;
            --warning: #9a6700;
            --danger: #cf222e;
            --code-bg: rgba(175, 184, 193, 0.2);
        }

        /* Dark Theme - Applied via system preference or manual selection */
        @media (prefers-color-scheme: dark) {
            :root:not([data-theme="light"]) {
                --bg-primary: #0d1117;
                --bg-surface: #161b22;
                --bg-elevated: #1c2128;
                --text-primary: #c9d1d9;
                --text-muted: #8b949e;
                --text-subtle: #6e7681;
                --border-default: #30363d;
                --border-muted: #21262d;
                --accent-primary: #58a6ff;
                --accent-secondary: #1f6feb;
                --success: #3fb950;
                --warning: #d29922;
                --danger: #f85149;
                --code-bg: rgba(110, 118, 129, 0.1);
            }
        }

        /* Manual theme overrides */
        :root[data-theme="dark"] {
            --bg-primary: #0d1117;
            --bg-surface: #161b22;
            --bg-elevated: #1c2128;
            --text-primary: #c9d1d9;
            --text-muted: #8b949e;
            --text-subtle: #6e7681;
            --border-default: #30363d;
            --border-muted: #21262d;
            --accent-primary: #58a6ff;
            --accent-secondary: #1f6feb;
            --success: #3fb950;
            --warning: #d29922;
            --danger: #f85149;
            --code-bg: rgba(110, 118, 129, 0.1);
        }

        :root[data-theme="light"] {
            --bg-primary: #ffffff;
            --bg-surface: #f6f8fa;
            --bg-elevated: #ffffff;
            --text-primary: #24292f;
            --text-muted: #57606a;
            --text-subtle: #6e7781;
            --border-default: #d0d7de;
            --border-muted: #d8dee4;
            --accent-primary: #0969da;
            --accent-secondary: #0550ae;
            --success: #1a7f37;
            --warning: #9a6700;
            --danger: #cf222e;
            --code-bg: rgba(175, 184, 193, 0.2);
        }

        /* Base Styles */
        * {
            box-sizing: border-box;
            margin: 0;
            padding: 0;
        }

        body {
            font-family: 'IBM Plex Sans', -apple-system, BlinkMacSystemFont, 'Segoe UI', system-ui, sans-serif;
            font-size: 16px;
            line-height: 1.6;
            margin: 0;
            padding: 24px;
            background: var(--bg-primary);
            color: var(--text-primary);
            -webkit-font-smoothing: antialiased;
            -moz-osx-font-smoothing: grayscale;
        }
        /* Layout */
        .container {
            display: grid;
            grid-template-columns: 280px 1fr 280px;
            gap: 24px;
            max-width: 1800px;
            margin: 0 auto;
        }

        .main-content {
            min-width: 0;
            position: relative;
        }

        /* Typography */
        h1 {
            font-family: 'Space Grotesk', sans-serif;
            font-size: 32px;
            font-weight: 700;
            color: var(--text-primary);
            margin: 0 0 8px 0;
            line-height: 1.2;
        }

        h3 {
            font-family: 'Space Grotesk', sans-serif;
            font-size: 18px;
            font-weight: 500;
            margin: 0 0 16px 0;
            letter-spacing: -0.01em;
        }

        /* Sidebar */
        .sidebar {
            background: var(--bg-surface);
            padding: 20px;
            border-radius: 6px;
            border: 1px solid var(--border-default);
            font-size: 14px;
            line-height: 1.6;
        }

        .sidebar h3 {
            color: var(--accent-primary);
            font-size: 16px;
            margin: 0 0 16px 0;
            font-weight: 600;
        }

        .sidebar .tip {
            margin-bottom: 16px;
            padding-bottom: 16px;
            border-bottom: 1px solid var(--border-muted);
        }

        .sidebar .tip:last-child {
            border-bottom: none;
            margin-bottom: 0;
            padding-bottom: 0;
        }

        .sidebar .tip-title {
            color: var(--text-primary);
            font-weight: 600;
            margin-bottom: 6px;
            font-size: 14px;
        }

        .sidebar .tip-content {
            color: var(--text-muted);
            font-size: 14px;
        }

        .sidebar code {
            font-family: 'JetBrains Mono', 'Consolas', monospace;
            background: var(--code-bg);
            padding: 2px 6px;
            border-radius: 3px;
            color: var(--accent-primary);
            font-size: 13px;
        }

        .sidebar kbd {
            font-family: 'JetBrains Mono', 'Consolas', monospace;
            background: var(--bg-elevated);
            padding: 2px 6px;
            border-radius: 3px;
            border: 1px solid var(--border-default);
            color: var(--text-primary);
            font-size: 12px;
        }
        /* Responsive Layout */
        @media (max-width: 1400px) {
            .container {
                grid-template-columns: 1fr;
            }
            .sidebar {
                display: none;
            }
        }

        /* Search Box */
        .search-box {
            width: 100%;
            padding: 12px 16px;
            font-size: 16px;
            margin-bottom: 20px;
            background: var(--bg-surface);
            color: var(--text-primary);
            border: 1px solid var(--border-default);
            border-radius: 6px;
            font-family: 'IBM Plex Sans', sans-serif;
            transition: border-color 0.2s ease, background-color 0.2s ease;
        }

        .search-box:focus {
            outline: none;
            border-color: var(--accent-primary);
            background: var(--bg-elevated);
        }

        .search-box::placeholder {
            color: var(--text-subtle);
        }

        /* Filters */
        .filters {
            margin-bottom: 24px;
            font-size: 14px;
            display: flex;
            flex-wrap: wrap;
            gap: 12px;
            align-items: center;
        }

        .filters label {
            color: var(--text-muted);
            display: inline-flex;
            align-items: center;
            gap: 8px;
        }

        .filters select,
        .filters input[type="date"] {
            background: var(--bg-surface);
            color: var(--text-primary);
            border: 1px solid var(--border-default);
            border-radius: 6px;
            padding: 6px 10px;
            font-family: 'IBM Plex Sans', sans-serif;
            font-size: 14px;
            cursor: pointer;
            transition: border-color 0.2s ease;
        }

        .filters select:focus,
        .filters input[type="date"]:focus {
            outline: none;
            border-color: var(--accent-primary);
        }

        .filters button {
            font-family: 'Space Grotesk', sans-serif;
            font-size: 14px;
            font-weight: 500;
            padding: 8px 16px;
            border: none;
            border-radius: 6px;
            cursor: pointer;
            transition: all 0.2s ease;
        }

        .filters button:first-of-type {
            background: var(--accent-secondary);
            color: white;
        }

        .filters button:first-of-type:hover {
            background: var(--accent-primary);
        }

        .filters button:nth-of-type(2) {
            background: var(--accent-secondary);
            color: white;
        }

        .filters button:nth-of-type(2):hover {
            background: var(--accent-primary);
        }

        .filters button:nth-of-type(3) {
            background: var(--success);
            color: white;
        }

        .filters button:nth-of-type(3):hover {
            background: #2ea043;
        }

        .filters button:nth-of-type(4) {
            background: var(--danger);
            color: white;
        }

        .filters button:nth-of-type(4):hover {
            background: #da3633;
        }

        /* Results Header */
        .results-header {
            color: var(--text-muted);
            font-size: 14px;
            margin-bottom: 16px;
            font-weight: 500;
        }

        /* Result Cards */
        .result {
            background: var(--bg-surface);
            border: 1px solid var(--border-default);
            border-left: 3px solid transparent;
            border-radius: 6px;
            padding: 16px 20px;
            margin-bottom: 16px;
            cursor: pointer;
            transition: all 0.2s ease;
        }

        .result.windows {
            border-left-color: var(--accent-primary);
        }

        .result.wsl {
            border-left-color: var(--warning);
        }

        .result:hover {
            background: var(--bg-elevated);
            border-color: var(--border-muted);
            transform: translateY(-2px);
            box-shadow: 0 4px 12px rgba(0, 0, 0, 0.3);
        }

        .result-title {
            font-family: 'Space Grotesk', sans-serif;
            font-weight: 600;
            font-size: 18px;
            color: var(--text-primary);
            margin-bottom: 8px;
            line-height: 1.3;
        }

        .result-meta {
            color: var(--text-muted);
            font-size: 14px;
            margin: 8px 0;
        }

        .result-meta .conv-id {
            font-family: 'JetBrains Mono', 'Consolas', monospace;
            color: var(--accent-primary);
            font-weight: 600;
            font-size: 13px;
        }

        .result-snippet {
            color: var(--text-muted);
            font-size: 16px;
            line-height: 1.6;
            margin-top: 12px;
        }

        .result-actions {
            display: flex;
            gap: 8px;
            margin-top: 12px;
        }

        .resume-btn {
            font-family: 'Space Grotesk', sans-serif;
            font-size: 13px;
            font-weight: 500;
            padding: 6px 14px;
            border: none;
            border-radius: 4px;
            background: var(--accent-primary);
            color: white;
            cursor: pointer;
            transition: all 0.2s ease;
            display: inline-flex;
            align-items: center;
            gap: 6px;
        }

        .resume-btn:hover {
            background: var(--accent-secondary);
            transform: translateY(-1px);
        }

        .resume-btn:active {
            transform: translateY(0);
        }

        .resume-btn.success {
            background: var(--success);
        }

        .resume-btn.error {
            background: var(--danger);
        }

        .tool-badge {
            font-family: 'JetBrains Mono', 'Consolas', monospace;
            font-size: 11px;
            font-weight: 600;
            padding: 3px 8px;
            border-radius: 3px;
            background: var(--code-bg);
            color: var(--accent-primary);
            text-transform: uppercase;
            letter-spacing: 0.5px;
        }

        .tool-badge.claude {
            background: rgba(88, 166, 255, 0.15);
            color: var(--accent-primary);
        }

        .tool-badge.vibe {
            background: rgba(255, 149, 0, 0.15);
            color: var(--warning);
        }

        /* Loading State */
        .loading {
            text-align: center;
            color: var(--text-muted);
            font-size: 16px;
            padding: 40px 20px;
        }

        /* Theme Toggle */
        .theme-toggle {
            position: absolute;
            top: 0;
            right: 0;
            display: flex;
            gap: 4px;
            background: var(--bg-surface);
            border: 1px solid var(--border-default);
            border-radius: 6px;
            padding: 4px;
            z-index: 100;
        }

        .theme-toggle button {
            font-family: 'Space Grotesk', sans-serif;
            font-size: 13px;
            font-weight: 500;
            padding: 6px 12px;
            border: none;
            border-radius: 4px;
            background: transparent;
            color: var(--text-muted);
            cursor: pointer;
            transition: all 0.2s ease;
        }

        .theme-toggle button:hover {
            color: var(--text-primary);
            background: var(--bg-elevated);
        }

        .theme-toggle button.active {
            background: var(--accent-primary);
            color: white;
        }
    </style>
</head>
<body>
    <div class="container">
        <!-- Left Sidebar: Search Tips -->
        <div class="sidebar">
            <h3>💡 Search Tips</h3>

            <div class="tip">
                <div class="tip-title">Search Modes</div>
                <div class="tip-content">
                    <strong>Hybrid</strong> - Best results (keyword + semantic)<br>
                    <strong>Semantic</strong> - Find by meaning/concept<br>
                    <strong>Keyword</strong> - Exact text matching
                </div>
            </div>

            <div class="tip">
                <div class="tip-title">Keyboard Shortcut</div>
                <div class="tip-content">
                    Press <kbd>Enter</kbd> in search box to search
                </div>
            </div>

            <div class="tip">
                <div class="tip-title">Live Indexing</div>
                <div class="tip-content">
                    New conversations are indexed automatically. In-progress sessions re-index 5 minutes after last edit.
                </div>
            </div>

            <div class="tip">
                <div class="tip-title">Missing Conversations?</div>
                <div class="tip-content">
                    Click <strong>Add Missing Conversations</strong> to index files not yet in the search index.
                </div>
            </div>

            <div class="tip">
                <div class="tip-title">Filter by Project</div>
                <div class="tip-content">
                    Use the Project dropdown to search within specific projects only.
                </div>
            </div>
        </div>

        <!-- Main Content -->
        <div class="main-content">
            <!-- Theme Toggle -->
            <div class="theme-toggle">
                <button onclick="setTheme('light')" data-theme="light">Light</button>
                <button onclick="setTheme('system')" data-theme="system" class="active">System</button>
                <button onclick="setTheme('dark')" data-theme="dark">Dark</button>
            </div>

            <h1 style="margin-bottom: 4px;"><span style="color: #4a9eff">sear</span><span style="background: linear-gradient(to right, #4a9eff, #ff9500); -webkit-background-clip: text; -webkit-text-fill-color: transparent; background-clip: text;">ch</span><span style="color: #ff9500">at</span></h1>
            <p style="margin: 0 0 20px 0; font-size: 13px; color: #888;">Semantic search for AI coding agent conversations — Claude Code + Mistral Vibe</p>
            <input type="text" id="search" class="search-box" placeholder="Search conversations..." />

            <div class="filters">
        <label>Mode: 
            <select id="mode">
                <option value="hybrid">Hybrid</option>
                <option value="semantic">Semantic</option>
                <option value="keyword">Keyword</option>
            </select>
        </label>
        
        <label>Project: 
            <select id="project">
                <option value="">All Projects</option>
            </select>
        </label>
        
        <label>Date: 
            <select id="date" onchange="toggleCustomDate()">
                <option value="">Any time</option>
                <option value="today">Today</option>
                <option value="week">Last 7 days</option>
                <option value="month">Last 30 days</option>
                <option value="custom">Custom range</option>
            </select>
        </label>
        
        <span id="customDateRange" style="display:none;">
            <label>From: <input type="date" id="dateFrom" /></label>
            <label>To: <input type="date" id="dateTo" /></label>
        </span>
        
        <label>Sort by: 
            <select id="sortBy">
                <option value="relevance">Relevance</option>
                <option value="date_newest">Date (newest)</option>
                <option value="date_oldest">Date (oldest)</option>
                <option value="messages">Message count</option>
            </select>
        </label>
        
        <button onclick="search()">Search</button>
        <button onclick="showAllConversations()" style="background: #2196F3; margin-left: 10px;">Show All</button>
        <button onclick="indexMissing()" style="background: #4CAF50; margin-left: 10px;" title="Safely add conversations that aren't in the index yet">Add Missing Conversations</button>
        <button onclick="shutdownServer()" style="background: #f44336; margin-left: 10px;" title="Stop the search server">Stop Server</button>
    </div>

    <div id="results"></div>
        </div>

        <!-- Right Sidebar: Claude Self-Search Integration -->
        <div class="sidebar">
            <h3>🤖 Claude Self-Search</h3>

            <div class="tip">
                <div class="tip-title">Enable in Claude Code</div>
                <div class="tip-content">
                    Add this to <code>~/.claude/CLAUDE.md</code> so Claude can search its own conversation history:
                </div>
            </div>

            <div class="tip">
                <div class="tip-title">Search API</div>
                <div class="tip-content">
                    <code>curl "http://localhost:8000/api/search?q=YOUR_QUERY&limit=5"</code>
                </div>
            </div>

            <div class="tip">
                <div class="tip-title">Get Conversation</div>
                <div class="tip-content">
                    <code>curl "http://localhost:8000/api/conversation/CONV_ID"</code>
                </div>
            </div>

            <div class="tip">
                <div class="tip-title">Full Instructions</div>
                <div class="tip-content">
                    See <code>CLAUDE.example.md</code> in the searchat repo for the complete template to add to your global CLAUDE.md file.
                </div>
            </div>

            <div class="tip">
                <div class="tip-title">Use Cases</div>
                <div class="tip-content">
                    • "Did we discuss X before?"<br>
                    • "Find past solutions for Y"<br>
                    • "How did we implement Z?"<br>
                    • Check previous debugging sessions
                </div>
            </div>

            <div class="tip">
                <div class="tip-title">API Parameters</div>
                <div class="tip-content">
                    <code>mode</code> - hybrid/semantic/keyword<br>
                    <code>limit</code> - max results (1-100)<br>
                    <code>project</code> - filter by project name
                </div>
            </div>
        </div>
    </div>

    <script>
        // Theme Management
        function setTheme(theme) {
            // Save preference
            localStorage.setItem('theme-preference', theme);

            // Apply theme
            applyTheme(theme);

            // Update button states
            document.querySelectorAll('.theme-toggle button').forEach(btn => {
                btn.classList.toggle('active', btn.dataset.theme === theme);
            });
        }

        function applyTheme(theme) {
            const root = document.documentElement;

            if (theme === 'system') {
                // Remove manual theme, let system preference take over
                root.removeAttribute('data-theme');
            } else {
                // Apply manual theme
                root.setAttribute('data-theme', theme);
            }
        }

        function initTheme() {
            // Get saved preference (default: system)
            const savedTheme = localStorage.getItem('theme-preference') || 'system';

            // Apply theme
            applyTheme(savedTheme);

            // Update button states
            document.querySelectorAll('.theme-toggle button').forEach(btn => {
                btn.classList.toggle('active', btn.dataset.theme === savedTheme);
            });
        }

        // Initialize theme on page load
        initTheme();

        // Save and restore search state
        function saveSearchState() {
            const state = {
                query: document.getElementById('search').value,
                mode: document.getElementById('mode').value,
                project: document.getElementById('project').value,
                date: document.getElementById('date').value,
                dateFrom: document.getElementById('dateFrom').value,
                dateTo: document.getElementById('dateTo').value,
                sortBy: document.getElementById('sortBy').value
            };
            sessionStorage.setItem('searchState', JSON.stringify(state));
        }
        
        function restoreSearchState() {
            const stateStr = sessionStorage.getItem('searchState');
            if (!stateStr) return false;
            
            const state = JSON.parse(stateStr);
            document.getElementById('search').value = state.query || '';
            document.getElementById('mode').value = state.mode || 'hybrid';
            document.getElementById('project').value = state.project || '';
            document.getElementById('date').value = state.date || '';
            document.getElementById('dateFrom').value = state.dateFrom || '';
            document.getElementById('dateTo').value = state.dateTo || '';
            document.getElementById('sortBy').value = state.sortBy || 'relevance';
            
            // Show custom date range if needed
            toggleCustomDate();
            
            // Re-run the search to restore results with proper click handlers
            if (state.query) {
                search();
                return true;
            }
            
            return false;
        }
        
        async function loadProjects() {
            const response = await fetch('/api/projects');
            const projects = await response.json();
            const select = document.getElementById('project');
            const currentValue = select.value;
            
            projects.forEach(p => {
                const option = document.createElement('option');
                option.value = p;
                option.textContent = p;
                select.appendChild(option);
            });
            
            // Restore previous value if it exists
            if (currentValue) select.value = currentValue;
        }
        
        async function search() {
            const query = document.getElementById('search').value;
            const project = document.getElementById('project').value;
            const date = document.getElementById('date').value;

            // Allow search if query OR any filter is set
            if (!query && !project && !date) {
                document.getElementById('results').innerHTML = '<div>Enter a search query or select a filter</div>';
                return;
            }

            const resultsDiv = document.getElementById('results');
            resultsDiv.innerHTML = '<div class="loading">Searching...</div>';
            
            const params = new URLSearchParams({
                q: query || '*',  // Use wildcard if no query
                mode: document.getElementById('mode').value,
                project: document.getElementById('project').value,
                date: document.getElementById('date').value,
                sort_by: document.getElementById('sortBy').value
            });
            
            // Add custom date range if selected
            if (document.getElementById('date').value === 'custom') {
                const dateFrom = document.getElementById('dateFrom').value;
                const dateTo = document.getElementById('dateTo').value;
                if (dateFrom) params.append('date_from', dateFrom);
                if (dateTo) params.append('date_to', dateTo);
            }
            
            const response = await fetch(`/api/search?${params}`);
            const data = await response.json();
            
            resultsDiv.innerHTML = '';
            if (data.results.length === 0) {
                resultsDiv.innerHTML = '<div>No results found</div>';
                saveSearchState();
                return;
            }
            
            resultsDiv.innerHTML = `<div class="results-header">Found ${data.total} results in ${Math.round(data.search_time_ms)}ms</div>`;
            
            data.results.forEach((r, index) => {
                const div = document.createElement('div');
                const isWSL = r.source === 'WSL';
                div.className = `result ${isWSL ? 'wsl' : 'windows'}`;
                div.id = `result-${index}`;
                // Get last segment of conversation ID
                const shortId = r.conversation_id.split('-').pop();

                // Detect tool from file_path
                const tool = r.file_path.endsWith('.jsonl') ? 'claude' : 'vibe';
                const toolLabel = tool === 'claude' ? 'Claude Code' : 'Vibe';

                div.innerHTML = `
                    <div class="result-title">${r.title}</div>
                    <div class="result-meta">
                        <span class="tool-badge ${tool}">${toolLabel}</span> •
                        <span class="conv-id">...${shortId}</span> •
                        ${r.project_id} •
                        ${r.message_count} msgs •
                        ${new Date(r.updated_at).toLocaleDateString()}
                    </div>
                    <div class="result-snippet">${r.snippet}</div>
                    <div class="result-actions">
                        <button class="resume-btn" data-conversation-id="${r.conversation_id}" onclick="event.stopPropagation(); resumeSession('${r.conversation_id}', this);">
                            ⚡ Resume Session
                        </button>
                    </div>
                `;
                div.onclick = () => {
                    saveSearchState();
                    sessionStorage.setItem('lastScrollPosition', window.scrollY);
                    sessionStorage.setItem('lastResultIndex', index);
                    window.location.href = `/conversation/${r.conversation_id}`;
                };
                resultsDiv.appendChild(div);
            });
            
            saveSearchState();
        }
        
        function toggleCustomDate() {
            const dateSelect = document.getElementById('date');
            const customRange = document.getElementById('customDateRange');
            customRange.style.display = dateSelect.value === 'custom' ? 'inline' : 'none';
        }

        async function resumeSession(conversationId, buttonElement) {
            const originalText = buttonElement.innerHTML;
            buttonElement.innerHTML = '⏳ Opening...';
            buttonElement.disabled = true;

            try {
                const response = await fetch('/api/resume', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ conversation_id: conversationId })
                });

                const data = await response.json();

                if (response.ok && data.success) {
                    buttonElement.innerHTML = '✓ Opened in terminal';
                    buttonElement.classList.add('success');
                    setTimeout(() => {
                        buttonElement.innerHTML = originalText;
                        buttonElement.classList.remove('success');
                        buttonElement.disabled = false;
                    }, 2000);
                } else {
                    throw new Error(data.detail || 'Failed to resume session');
                }
            } catch (error) {
                buttonElement.innerHTML = '❌ Failed - check console';
                buttonElement.classList.add('error');
                console.error('Resume error:', error);
                setTimeout(() => {
                    buttonElement.innerHTML = originalText;
                    buttonElement.classList.remove('error');
                    buttonElement.disabled = false;
                }, 3000);
            }
        }

        async function showAllConversations() {
            const resultsDiv = document.getElementById('results');
            resultsDiv.innerHTML = '<div class="loading">Loading all conversations...</div>';

            const sortBy = document.getElementById('sortBy').value;

            // Map sort values to API parameters
            let apiSortBy = 'length';
            if (sortBy === 'date_newest') apiSortBy = 'date_newest';
            else if (sortBy === 'date_oldest') apiSortBy = 'date_oldest';
            else if (sortBy === 'messages') apiSortBy = 'length';

            const params = new URLSearchParams({ sort_by: apiSortBy });

            try {
                const response = await fetch(`/api/conversations/all?${params}`);
                const data = await response.json();

                resultsDiv.innerHTML = '';
                if (data.results.length === 0) {
                    resultsDiv.innerHTML = '<div>No conversations found</div>';
                    return;
                }

                resultsDiv.innerHTML = `<div class="results-header">Showing all ${data.total} conversations (sorted by ${apiSortBy})</div>`;

                data.results.forEach((r, index) => {
                    const div = document.createElement('div');
                    const isWSL = r.source === 'WSL';
                    div.className = `result ${isWSL ? 'wsl' : 'windows'}`;
                    div.id = `result-${index}`;
                    const shortId = r.conversation_id.split('-').pop();

                    // Detect tool from file_path
                    const tool = r.file_path.endsWith('.jsonl') ? 'claude' : 'vibe';
                    const toolLabel = tool === 'claude' ? 'Claude Code' : 'Vibe';

                    div.innerHTML = `
                        <div class="result-title">${r.title}</div>
                        <div class="result-meta">
                            <span class="tool-badge ${tool}">${toolLabel}</span> •
                            <span class="conv-id">...${shortId}</span> •
                            ${r.project_id} •
                            ${r.message_count} msgs •
                            ${new Date(r.updated_at).toLocaleDateString()}
                        </div>
                        <div class="result-snippet">${r.snippet}</div>
                        <div class="result-actions">
                            <button class="resume-btn" data-conversation-id="${r.conversation_id}" onclick="event.stopPropagation(); resumeSession('${r.conversation_id}', this);">
                                ⚡ Resume Session
                            </button>
                        </div>
                    `;
                    div.onclick = () => {
                        saveSearchState();
                        sessionStorage.setItem('lastScrollPosition', window.scrollY);
                        sessionStorage.setItem('lastResultIndex', index);
                        window.location.href = `/conversation/${r.conversation_id}`;
                    };
                    resultsDiv.appendChild(div);
                });
            } catch (error) {
                resultsDiv.innerHTML = `<div style="color: #f44336;">Error: ${error.message}</div>`;
            }
        }

        async function indexMissing() {
            const resultsDiv = document.getElementById('results');
            resultsDiv.innerHTML = '<div class="loading">Scanning for missing conversations... This may take a minute...</div>';

            try {
                const response = await fetch('/api/index_missing', { method: 'POST' });
                const data = await response.json();

                if (data.success) {
                    if (data.new_conversations === 0) {
                        resultsDiv.innerHTML = `
                            <div class="results-header" style="background: #4CAF50; padding: 15px;">
                                <strong>✓ All conversations are already indexed</strong>
                                <div style="margin-top: 8px; opacity: 0.9;">
                                    Total files: ${data.total_files} | Already indexed: ${data.already_indexed}
                                </div>
                                <div style="margin-top: 8px; font-size: 13px; opacity: 0.8;">
                                    The live file watcher will automatically index new conversations as you create them.
                                </div>
                            </div>
                        `;
                    } else {
                        resultsDiv.innerHTML = `
                            <div class="results-header" style="background: #4CAF50; padding: 15px;">
                                <strong>✓ Added ${data.new_conversations} conversations to index</strong>
                                <div style="margin-top: 8px; opacity: 0.9;">
                                    Total files: ${data.total_files} | Previously indexed: ${data.already_indexed} | Time: ${data.time_seconds}s
                                </div>
                                <div style="margin-top: 8px; font-size: 13px; opacity: 0.8;">
                                    Your new conversations are now searchable!
                                </div>
                            </div>
                        `;

                        // Reload projects list
                        const projectSelect = document.getElementById('project');
                        projectSelect.innerHTML = '<option value="">All Projects</option>';
                        await loadProjects();
                    }
                } else {
                    resultsDiv.innerHTML = '<div style="color: #f44336;">Indexing failed</div>';
                }
            } catch (error) {
                resultsDiv.innerHTML = `<div style="color: #f44336;">Error: ${error.message}</div>`;
            }
        }

        async function shutdownServer(force = false) {
            if (!force && !confirm('Stop the search server? You will need to restart it from the terminal.')) {
                return;
            }

            const resultsDiv = document.getElementById('results');
            resultsDiv.innerHTML = '<div class="loading">Checking server status...</div>';

            try {
                const url = force ? '/api/shutdown?force=true' : '/api/shutdown';
                const response = await fetch(url, { method: 'POST' });
                const data = await response.json();

                if (data.success) {
                    const warningStyle = data.forced ?
                        'background: #ff9800; border-left-color: #ff5722;' :
                        'background: #f44336;';

                    const warningMsg = data.forced ?
                        '<div style="margin-top: 8px; color: #fff; font-weight: 600;">⚠ FORCED SHUTDOWN - Indexing was interrupted. Index may be inconsistent.</div>' :
                        '';

                    resultsDiv.innerHTML = `
                        <div class="results-header" style="${warningStyle} padding: 15px;">
                            <strong>✓ Server shutting down</strong>
                            ${warningMsg}
                            <div style="margin-top: 8px; opacity: 0.9;">
                                You can close this window. To restart, run: <code style="background: #333; padding: 2px 6px;">searchat-web</code>
                            </div>
                        </div>
                    `;
                } else if (data.indexing_in_progress) {
                    // Indexing is in progress - offer options
                    resultsDiv.innerHTML = `
                        <div class="results-header" style="background: #ff9800; padding: 15px; border-left: 3px solid #ff5722;">
                            <strong>⚠ Indexing in Progress</strong>
                            <div style="margin-top: 8px;">
                                <strong>Operation:</strong> ${data.operation}<br>
                                <strong>Files:</strong> ${data.files_total}<br>
                                <strong>Elapsed:</strong> ${data.elapsed_seconds}s
                            </div>
                            <div style="margin-top: 12px; color: #fff;">
                                Shutting down during indexing may corrupt data.
                            </div>
                            <div style="margin-top: 12px;">
                                <button onclick="shutdownServer(true)" style="background: #f44336; color: white; border: none; padding: 8px 16px; cursor: pointer; margin-right: 10px;">
                                    Force Stop (Unsafe)
                                </button>
                                <button onclick="document.getElementById('results').innerHTML = ''" style="background: #4CAF50; color: white; border: none; padding: 8px 16px; cursor: pointer;">
                                    Wait for Completion
                                </button>
                            </div>
                        </div>
                    `;
                } else {
                    resultsDiv.innerHTML = '<div style="color: #f44336;">Shutdown failed</div>';
                }
            } catch (error) {
                // Server likely already shut down, which is expected
                resultsDiv.innerHTML = `
                    <div class="results-header" style="background: #f44336; padding: 15px;">
                        <strong>✓ Server stopped</strong>
                        <div style="margin-top: 8px; opacity: 0.9;">
                            You can close this window. To restart, run: <code style="background: #333; padding: 2px 6px;">searchat-web</code>
                        </div>
                    </div>
                `;
            }
        }

        document.getElementById('search').addEventListener('keypress', (e) => {
            if (e.key === 'Enter') search();
        });
        
        // On page load, restore state if available
        window.addEventListener('load', async () => {
            await loadProjects();
            
            // Check if we're returning from a conversation view
            const searchState = sessionStorage.getItem('searchState');
            if (searchState) {
                await restoreSearchState();
                
                // After search completes, restore position and highlight
                setTimeout(() => {
                    const scrollPos = sessionStorage.getItem('lastScrollPosition');
                    if (scrollPos) {
                        window.scrollTo(0, parseInt(scrollPos));
                    }
                    
                    // Highlight last clicked result
                    const lastIndex = sessionStorage.getItem('lastResultIndex');
                    if (lastIndex) {
                        const element = document.getElementById(`result-${lastIndex}`);
                        if (element) {
                            element.style.border = '2px solid #4CAF50';
                        }
                    }
                }, 500);
            }
        });
    </script>
</body>
</html>
        """)


@app.get("/api/search")
async def search(
    q: str = Query(..., description="Search query"),
    mode: str = Query("hybrid", description="Search mode: hybrid, semantic, or keyword"),
    project: str | None = Query(None, description="Filter by project"),
    date: str | None = Query(None, description="Date filter: today, week, month, or custom"),
    date_from: str | None = Query(None, description="Custom date from (YYYY-MM-DD)"),
    date_to: str | None = Query(None, description="Custom date to (YYYY-MM-DD)"),
    tool: str | None = Query(None, description="Filter by tool: claude, vibe, opencode"),
    sort_by: str = Query("relevance", description="Sort by: relevance, date_newest, date_oldest, messages"),
    limit: int = Query(100, description="Max results to return (1-100)", ge=1, le=100)
):
    """Search conversations"""
    try:
        # Convert mode string to SearchMode enum
        mode_map = {
            "hybrid": SearchMode.HYBRID,
            "semantic": SearchMode.SEMANTIC,
            "keyword": SearchMode.KEYWORD
        }
        search_mode = mode_map.get(mode, SearchMode.HYBRID)
        
        # Build filters
        filters = SearchFilters()
        if project:
            filters.project_ids = [project]

        if tool:
            tool_value = tool.lower()
            if tool_value not in ("claude", "vibe", "opencode"):
                raise HTTPException(status_code=400, detail="Invalid tool filter")
            filters.tool = tool_value
        
        # Handle date filtering
        if date == "custom" and (date_from or date_to):
            # Custom date range
            if date_from:
                filters.date_from = datetime.fromisoformat(date_from)
            if date_to:
                # Add 1 day to include the entire end date
                filters.date_to = datetime.fromisoformat(date_to) + timedelta(days=1)
        elif date:
            # Preset date ranges
            now = datetime.now()
            if date == "today":
                filters.date_from = now.replace(hour=0, minute=0, second=0, microsecond=0)
                filters.date_to = now
            elif date == "week":
                filters.date_from = now - timedelta(days=7)
                filters.date_to = now
            elif date == "month":
                filters.date_from = now - timedelta(days=30)
                filters.date_to = now
                
        # Execute search
        results = search_engine.search(q, mode=search_mode, filters=filters)
        
        # Sort results based on sort_by parameter
        sorted_results = results.results.copy()
        if sort_by == "date_newest":
            sorted_results.sort(key=lambda r: r.updated_at, reverse=True)
        elif sort_by == "date_oldest":
            sorted_results.sort(key=lambda r: r.updated_at, reverse=False)
        elif sort_by == "messages":
            sorted_results.sort(key=lambda r: r.message_count, reverse=True)
        # else keep default relevance sorting (by score)
        
        # Convert results to response format
        response_results = []
        for r in sorted_results[:limit]:
            file_path_lower = r.file_path.lower()
            if r.file_path.endswith('.jsonl'):
                tool_name = "claude"
            elif "/.local/share/opencode/" in file_path_lower:
                tool_name = "opencode"
            else:
                tool_name = "vibe"

            if "/home/" in file_path_lower or "wsl" in file_path_lower:
                source = "WSL"
            else:
                source = "WIN"

            response_results.append(SearchResultResponse(
                conversation_id=r.conversation_id,
                project_id=r.project_id,
                title=r.title,
                created_at=r.created_at.isoformat(),
                updated_at=r.updated_at.isoformat(),
                message_count=r.message_count,
                file_path=r.file_path,
                snippet=r.snippet,
                score=r.score,
                message_start_index=r.message_start_index,
                message_end_index=r.message_end_index,
                source=source,
                tool=tool_name,
            ))
            
        return {
            "results": response_results,
            "total": results.total_count,
            "search_time_ms": results.search_time_ms
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/projects")
async def get_projects():
    """Get list of all projects"""
    global projects_cache
    if projects_cache is None:
        store = deps.get_duckdb_store()
        projects_cache = store.list_projects()
    return projects_cache


@app.get("/api/conversations/all")
async def get_all_conversations(
    sort_by: str = Query("length", description="Sort by: length, date_newest, date_oldest, title"),
    project: str | None = Query(None, description="Filter by project"),
    date: str | None = Query(None, description="Date filter: today, week, month, or custom"),
    date_from: str | None = Query(None, description="Custom date from (YYYY-MM-DD)"),
    date_to: str | None = Query(None, description="Custom date to (YYYY-MM-DD)"),
    tool: str | None = Query(None, description="Filter by tool: claude, vibe, opencode"),
    limit: int | None = Query(None, ge=1, le=5000, description="Max results to return"),
    offset: int = Query(0, ge=0, description="Offset for pagination"),
):
    """Get all conversations with sorting"""
    try:
        store = deps.get_duckdb_store()

        date_from_dt = None
        date_to_dt = None
        if date == "custom" and (date_from or date_to):
            if date_from:
                date_from_dt = datetime.fromisoformat(date_from)
            if date_to:
                date_to_dt = datetime.fromisoformat(date_to) + timedelta(days=1)
        elif date:
            now = datetime.now()
            if date == "today":
                date_from_dt = now.replace(hour=0, minute=0, second=0, microsecond=0)
                date_to_dt = now
            elif date == "week":
                date_from_dt = now - timedelta(days=7)
                date_to_dt = now
            elif date == "month":
                date_from_dt = now - timedelta(days=30)
                date_to_dt = now

        if tool:
            tool_value = tool.lower()
            if tool_value not in ("claude", "vibe", "opencode"):
                raise HTTPException(status_code=400, detail="Invalid tool filter")
            tool = tool_value

        count_kwargs = {
            "project_id": project,
            "date_from": date_from_dt,
            "date_to": date_to_dt,
        }
        if tool is not None:
            count_kwargs["tool"] = tool
        total = store.count_conversations(**count_kwargs)

        list_kwargs = {
            "sort_by": sort_by,
            "project_id": project,
            "date_from": date_from_dt,
            "date_to": date_to_dt,
            "limit": limit,
            "offset": offset,
        }
        if tool is not None:
            list_kwargs["tool"] = tool
        rows = store.list_conversations(**list_kwargs)

        response_results = []
        for row in rows:
            file_path = row["file_path"]
            file_path_lower = file_path.lower()
            if file_path.endswith('.jsonl'):
                tool_name = "claude"
            elif "/.local/share/opencode/" in file_path_lower:
                tool_name = "opencode"
            else:
                tool_name = "vibe"

            if "/home/" in file_path_lower or "wsl" in file_path_lower:
                source = "WSL"
            else:
                source = "WIN"

            full_text = row.get("full_text") or ""
            response_results.append(
                SearchResultResponse(
                    conversation_id=row["conversation_id"],
                    project_id=row["project_id"],
                    title=row["title"],
                    created_at=row["created_at"].isoformat(),
                    updated_at=row["updated_at"].isoformat(),
                    message_count=row["message_count"],
                    file_path=file_path,
                    snippet=full_text[:200] + ("..." if len(full_text) > 200 else ""),
                    score=0.0,
                    message_start_index=None,
                    message_end_index=None,
                    source=source,
                    tool=tool_name,
                )
            )

        return {
            "results": response_results,
            "total": total,
            "search_time_ms": 0,
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/conversation/{conversation_id}")
async def get_conversation(conversation_id: str):
    """Get a specific conversation"""
    import logging
    logger = logging.getLogger(__name__)

    try:
        store = deps.get_duckdb_store()
        conv = store.get_conversation_meta(conversation_id)
        if conv is None:
            logger.warning(f"Conversation not found in index: {conversation_id}")
            raise HTTPException(status_code=404, detail="Conversation not found in index")

        file_path = conv["file_path"]

        # Check if file exists
        if not Path(file_path).exists():
            logger.error(f"Conversation file not found: {file_path} (conversation_id: {conversation_id})")
            raise HTTPException(
                status_code=404,
                detail=f"Conversation file not found. The file may have been moved or deleted: {file_path}"
            )

        messages = []
        if file_path.endswith('.jsonl'):
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    lines = [json.loads(line) for line in f]
            except json.JSONDecodeError as e:
                logger.error(f"Invalid JSON in conversation file {file_path}: {e}")
                raise HTTPException(
                    status_code=500,
                    detail=f"Failed to parse conversation file (invalid JSON at line {e.lineno})"
                )
            except UnicodeDecodeError as e:
                logger.error(f"Encoding error reading {file_path}: {e}")
                raise HTTPException(
                    status_code=500,
                    detail="Failed to read conversation file (encoding error)"
                )

            for entry in lines:
                if entry.get('type') in ('user', 'assistant'):
                    raw_content = entry.get('message', {}).get('content', '')
                    if isinstance(raw_content, str):
                        content = raw_content
                    elif isinstance(raw_content, list):
                        content = '\n\n'.join(
                            block.get('text', '')
                            for block in raw_content
                            if block.get('type') == 'text'
                        )
                    else:
                        content = ''

                    if content:
                        messages.append(ConversationMessage(
                            role=entry.get('type'),
                            content=content,
                            timestamp=entry.get('timestamp', '')
                        ))
        elif file_path.endswith('.json'):
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
            except json.JSONDecodeError as e:
                logger.error(f"Invalid JSON in conversation file {file_path}: {e}")
                raise HTTPException(
                    status_code=500,
                    detail=f"Failed to parse conversation file (invalid JSON at line {e.lineno})"
                )
            except UnicodeDecodeError as e:
                logger.error(f"Encoding error reading {file_path}: {e}")
                raise HTTPException(
                    status_code=500,
                    detail="Failed to read conversation file (encoding error)"
                )

            file_path_lower = file_path.lower()
            is_opencode = "projectID" in data or "/.local/share/opencode/" in file_path_lower
            if is_opencode:
                session_id = data.get("id") or data.get("sessionID") or conversation_id
                messages = _load_opencode_messages(file_path, session_id)
            else:
                messages = _extract_vibe_messages(data)

        logger.info(f"Successfully loaded conversation {conversation_id} with {len(messages)} messages")

        file_path_lower = file_path.lower()
        if file_path.endswith('.jsonl'):
            tool_name = "claude"
        elif "/.local/share/opencode/" in file_path_lower:
            tool_name = "opencode"
        else:
            tool_name = "vibe"

        project_path = None
        if tool_name == "opencode":
            project_path = _load_opencode_project_path(file_path)
        elif tool_name == "vibe":
            project_path = _load_vibe_project_path(file_path)

        return ConversationResponse(
            conversation_id=conversation_id,
            title=conv['title'],
            project_id=conv['project_id'],
            project_path=project_path,
            file_path=conv['file_path'],
            message_count=len(messages),
            tool=tool_name,
            messages=messages
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error loading conversation {conversation_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


@app.get("/api/statistics")
async def get_statistics():
    """Get search statistics"""
    store = deps.get_duckdb_store()
    stats = store.get_statistics()

    return {
        "total_conversations": stats.total_conversations,
        "total_messages": stats.total_messages,
        "avg_messages": stats.avg_messages,
        "total_projects": stats.total_projects,
        "earliest_date": stats.earliest_date,
        "latest_date": stats.latest_date,
    }


@app.post("/api/resume")
async def resume_session(request: ResumeRequest):
    """Resume a conversation session in its original tool (Claude Code or Vibe)"""
    import logging

    logger = logging.getLogger(__name__)

    try:
        store = deps.get_duckdb_store()
        conv = store.get_conversation_meta(request.conversation_id)
        if conv is None:
            raise HTTPException(status_code=404, detail="Conversation not found")

        file_path = conv["file_path"]
        session_id = conv["conversation_id"]

        # Extract working directory from conversation file
        cwd = None

        if file_path.endswith('.jsonl'):
            # Claude Code - read lines until we find one with cwd
            tool = 'claude'
            with open(file_path, 'r', encoding='utf-8') as f:
                for line in f:
                    entry = json.loads(line)
                    if 'cwd' in entry:
                        cwd = entry['cwd']
                        break
            command = f'claude --resume {session_id}'
        elif file_path.endswith('.json'):
            # Vibe or OpenCode - read JSON metadata
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            if 'projectID' in data and 'sessionID' in data:
                tool = 'opencode'
                cwd = data.get('directory')
                command = f'opencode --resume {session_id}'
            else:
                tool = 'vibe'
                cwd = data.get('metadata', {}).get('environment', {}).get('working_directory', None)
                command = f'vibe --resume {session_id}'
        else:
            raise HTTPException(status_code=400, detail=f"Unknown conversation format: {file_path}")

        # Normalize path for current platform
        if cwd:
            cwd = platform_manager.normalize_path(cwd)

        logger.info(f"Resuming {tool} session {session_id}")
        logger.info(f"  Platform: {platform_manager.platform}")
        logger.info(f"  Original CWD: {cwd}")
        logger.info(f"  Command: {command}")

        # Open terminal with command using platform-specific implementation
        # Path translation happens automatically in open_terminal_with_command
        platform_manager.open_terminal_with_command(command, cwd)

        return {
            "success": True,
            "tool": tool,
            "cwd": cwd,
            "command": command,
            "platform": platform_manager.platform
        }

    except HTTPException:
        raise
    except FileNotFoundError as e:
        # Command not found (claude or vibe not installed)
        logger.error(f"Command not found: {e}")
        tool_name = locals().get('tool', 'claude/vibe')
        raise HTTPException(
            status_code=500,
            detail=f"Failed to execute command. Make sure {tool_name} is installed and in PATH."
        )
    except Exception as e:
        logger.error(f"Failed to resume session {request.conversation_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/reindex")
async def reindex():
    """Rebuild the search index - DISABLED FOR DATA SAFETY"""
    # SAFETY GUARD: Block all reindexing to protect irreplaceable conversation data
    raise HTTPException(
        status_code=403,
        detail="BLOCKED: Reindexing disabled to protect irreplaceable conversation data. "
               "Source JSONLs are missing - rebuilding would cause data loss."
    )


@app.post("/api/index_missing")
async def index_missing():
    """Index conversations that aren't already indexed (append-only, safe)"""
    global projects_cache, indexing_state
    import logging
    logger = logging.getLogger(__name__)

    try:
        import time
        start_time = time.time()

        # Get all conversation files
        all_files = []

        # Claude Code conversations (.jsonl)
        for claude_dir in PathResolver.resolve_claude_dirs(config):
            try:
                jsonl_files = list(claude_dir.rglob("*.jsonl"))
                all_files.extend([str(f) for f in jsonl_files])
            except Exception as e:
                logger.warning(f"Error scanning {claude_dir}: {e}")

        # Vibe sessions (.json)
        for vibe_dir in PathResolver.resolve_vibe_dirs():
            try:
                json_files = list(vibe_dir.glob("*.json"))
                all_files.extend([str(f) for f in json_files])
            except Exception as e:
                logger.warning(f"Error scanning {vibe_dir}: {e}")

        # OpenCode sessions (.json)
        for opencode_dir in PathResolver.resolve_opencode_dirs(config):
            storage_session_dir = opencode_dir / "storage" / "session"
            if not storage_session_dir.exists():
                continue
            try:
                session_files = list(storage_session_dir.glob("*/*.json"))
                all_files.extend([str(f) for f in session_files])
            except Exception as e:
                logger.warning(f"Error scanning {storage_session_dir}: {e}")

        # Get already indexed files
        indexed_paths = indexer.get_indexed_file_paths()

        # Find new files
        new_files = [f for f in all_files if f not in indexed_paths]

        if not new_files:
            return {
                "success": True,
                "new_conversations": 0,
                "total_files": len(all_files),
                "already_indexed": len(indexed_paths),
                "message": "All conversations are already indexed"
            }

        # Mark indexing in progress
        indexing_state["in_progress"] = True
        indexing_state["operation"] = "manual_index"
        indexing_state["started_at"] = datetime.now().isoformat()
        indexing_state["files_total"] = len(new_files)
        indexing_state["files_processed"] = 0

        # Index new files
        logger.info(f"Indexing {len(new_files)} missing conversations")
        stats = indexer.index_append_only(new_files)

        # Reload search engine to pick up new data
        search_engine.refresh_index()

        # Clear projects cache
        projects_cache = None

        elapsed_time = time.time() - start_time

        return {
            "success": True,
            "new_conversations": stats.new_conversations,
            "total_files": len(all_files),
            "already_indexed": len(indexed_paths),
            "time_seconds": round(elapsed_time, 2),
            "message": f"Added {stats.new_conversations} conversations to index"
        }

    except Exception as e:
        logger.error(f"Error indexing missing conversations: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        # Mark indexing complete
        indexing_state["in_progress"] = False
        indexing_state["operation"] = None


@app.post("/api/shutdown")
async def shutdown_server(background_tasks: BackgroundTasks, force: bool = False):
    """Gracefully shutdown the server with safety checks"""
    import logging
    logger = logging.getLogger(__name__)
    global indexing_state

    # Check if indexing is in progress
    if indexing_state["in_progress"] and not force:
        # Calculate elapsed time
        started = datetime.fromisoformat(indexing_state["started_at"])
        elapsed = (datetime.now() - started).total_seconds()

        return {
            "success": False,
            "indexing_in_progress": True,
            "operation": indexing_state["operation"],
            "files_total": indexing_state["files_total"],
            "elapsed_seconds": round(elapsed, 1),
            "message": f"Indexing in progress ({indexing_state['operation']}). "
                      f"Processing {indexing_state['files_total']} files. "
                      f"Use force=true to shutdown anyway (may corrupt data)."
        }

    def shutdown():
        """Shutdown function to run in background"""
        import time
        time.sleep(0.5)  # Give time for response to be sent

        if force and indexing_state["in_progress"]:
            logger.warning(f"FORCED shutdown during indexing operation: {indexing_state['operation']}")
        else:
            logger.info("Server shutdown requested via API")

        # Stop watcher if running
        global watcher
        if watcher and watcher.is_running:
            logger.info("Stopping file watcher...")
            watcher.stop()

        logger.info("Shutting down server...")
        os.kill(os.getpid(), signal.SIGTERM)

    background_tasks.add_task(shutdown)

    if force and indexing_state["in_progress"]:
        return {
            "success": True,
            "forced": True,
            "message": "Force shutdown initiated (indexing interrupted - data may be inconsistent)"
        }
    else:
        return {
            "success": True,
            "forced": False,
            "message": "Server shutting down gracefully..."
        }


@app.post("/api/backup/create")
async def create_backup(backup_name: str | None = None):
    """Create a new backup of the index and data"""
    import logging
    logger = logging.getLogger(__name__)

    try:
        logger.info(f"Creating backup: {backup_name or 'auto'}")
        metadata = backup_manager.create_backup(backup_name=backup_name)

        return {
            "success": True,
            "backup": metadata.to_dict(),
            "message": f"Backup created: {metadata.backup_path.name}"
        }

    except Exception as e:
        logger.error(f"Failed to create backup: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/backup/list")
async def list_backups():
    """List all available backups"""
    try:
        backups = backup_manager.list_backups()

        return {
            "backups": [b.to_dict() for b in backups],
            "total": len(backups),
            "backup_directory": str(backup_manager.backup_dir)
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/backup/restore")
async def restore_backup(backup_name: str):
    """Restore from a backup"""
    import logging
    logger = logging.getLogger(__name__)

    try:
        backup_path = backup_manager.backup_dir / backup_name

        if not backup_path.exists():
            raise HTTPException(status_code=404, detail=f"Backup not found: {backup_name}")

        logger.info(f"Restoring from backup: {backup_name}")

        pre_restore_metadata = backup_manager.restore_from_backup(
            backup_path=backup_path,
            create_pre_restore_backup=True
        )

        # Reload search engine to pick up restored data
        search_engine.refresh_index()

        # Clear projects cache
        global projects_cache
        projects_cache = None

        result = {
            "success": True,
            "restored_from": backup_name,
            "message": f"Successfully restored from backup: {backup_name}"
        }

        if pre_restore_metadata:
            result["pre_restore_backup"] = pre_restore_metadata.to_dict()

        return result

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to restore backup: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/api/backup/delete/{backup_name}")
async def delete_backup(backup_name: str):
    """Delete a backup"""
    import logging
    logger = logging.getLogger(__name__)

    try:
        backup_path = backup_manager.backup_dir / backup_name

        if not backup_path.exists():
            raise HTTPException(status_code=404, detail=f"Backup not found: {backup_name}")

        logger.info(f"Deleting backup: {backup_name}")
        backup_manager.delete_backup(backup_path)

        return {
            "success": True,
            "deleted": backup_name,
            "message": f"Backup deleted: {backup_name}"
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to delete backup: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/conversation/{conversation_id}")
async def conversation_page(conversation_id: str):
    """Serve conversation viewer page"""
    return HTMLResponse(f"""
<!DOCTYPE html>
<html>
<head>
    <title>Searchat - Conversation</title>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">

    <!-- Preload fonts -->
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@400;500;700&family=IBM+Plex+Sans:wght@400;500;600&family=JetBrains+Mono:wght@400;500&display=swap" rel="stylesheet">

    <style>
        /* CSS Variables - Light Theme (GitHub Light) */
        :root {{
            --bg-primary: #ffffff;
            --bg-surface: #f6f8fa;
            --bg-elevated: #ffffff;
            --text-primary: #24292f;
            --text-muted: #57606a;
            --text-subtle: #6e7781;
            --border-default: #d0d7de;
            --border-muted: #d8dee4;
            --accent-primary: #0969da;
            --accent-secondary: #0550ae;
            --success: #1a7f37;
            --warning: #9a6700;
            --danger: #cf222e;
            --code-bg: rgba(175, 184, 193, 0.2);
        }}

        /* Dark Theme - Applied via system preference or manual selection */
        @media (prefers-color-scheme: dark) {{
            :root:not([data-theme="light"]) {{
                --bg-primary: #0d1117;
                --bg-surface: #161b22;
                --bg-elevated: #1c2128;
                --text-primary: #c9d1d9;
                --text-muted: #8b949e;
                --text-subtle: #6e7681;
                --border-default: #30363d;
                --border-muted: #21262d;
                --accent-primary: #58a6ff;
                --accent-secondary: #1f6feb;
                --success: #3fb950;
                --warning: #d29922;
                --danger: #f85149;
                --code-bg: rgba(110, 118, 129, 0.1);
            }}
        }}

        /* Manual theme overrides */
        :root[data-theme="dark"] {{
            --bg-primary: #0d1117;
            --bg-surface: #161b22;
            --bg-elevated: #1c2128;
            --text-primary: #c9d1d9;
            --text-muted: #8b949e;
            --text-subtle: #6e7681;
            --border-default: #30363d;
            --border-muted: #21262d;
            --accent-primary: #58a6ff;
            --accent-secondary: #1f6feb;
            --success: #3fb950;
            --warning: #d29922;
            --danger: #f85149;
            --code-bg: rgba(110, 118, 129, 0.1);
        }}

        :root[data-theme="light"] {{
            --bg-primary: #ffffff;
            --bg-surface: #f6f8fa;
            --bg-elevated: #ffffff;
            --text-primary: #24292f;
            --text-muted: #57606a;
            --text-subtle: #6e7781;
            --border-default: #d0d7de;
            --border-muted: #d8dee4;
            --accent-primary: #0969da;
            --accent-secondary: #0550ae;
            --success: #1a7f37;
            --warning: #9a6700;
            --danger: #cf222e;
            --code-bg: rgba(175, 184, 193, 0.2);
        }}

        * {{
            box-sizing: border-box;
            margin: 0;
            padding: 0;
        }}

        body {{
            font-family: 'IBM Plex Sans', -apple-system, BlinkMacSystemFont, 'Segoe UI', system-ui, sans-serif;
            font-size: 16px;
            line-height: 1.6;
            max-width: 1000px;
            margin: 0 auto;
            padding: 24px;
            background: var(--bg-primary);
            color: var(--text-primary);
            -webkit-font-smoothing: antialiased;
            -moz-osx-font-smoothing: grayscale;
            position: relative;
        }}

        .back-button {{
            font-family: 'Space Grotesk', sans-serif;
            padding: 10px 20px;
            background: var(--accent-secondary);
            color: white;
            text-decoration: none;
            font-size: 14px;
            font-weight: 500;
            display: inline-block;
            margin-bottom: 24px;
            border-radius: 6px;
            transition: background-color 0.2s ease;
        }}

        .back-button:hover {{
            background: var(--accent-primary);
        }}

        .header {{
            background: var(--bg-surface);
            padding: 20px;
            margin-bottom: 24px;
            border: 1px solid var(--border-default);
            border-left: 3px solid var(--accent-primary);
            border-radius: 6px;
        }}

        .header h2 {{
            font-family: 'Space Grotesk', sans-serif;
            color: var(--text-primary);
            margin: 0 0 12px 0;
            font-size: 24px;
            font-weight: 600;
        }}

        .header div {{
            color: var(--text-muted);
            font-size: 14px;
        }}

        .message {{
            background: var(--bg-surface);
            border: 1px solid var(--border-default);
            border-left: 3px solid transparent;
            border-radius: 6px;
            padding: 20px;
            margin-bottom: 20px;
        }}

        .message.user {{
            border-left-color: var(--success);
        }}

        .message.assistant {{
            border-left-color: var(--accent-primary);
        }}

        .role {{
            font-family: 'Space Grotesk', sans-serif;
            font-weight: 600;
            color: var(--text-muted);
            margin-bottom: 12px;
            font-size: 14px;
            text-transform: uppercase;
            letter-spacing: 0.5px;
        }}

        .content {{
            white-space: pre-wrap;
            font-family: 'IBM Plex Sans', sans-serif;
            color: var(--text-primary);
            font-size: 16px;
            line-height: 1.6;
        }}

        /* Theme Toggle */
        .theme-toggle {{
            position: absolute;
            top: 0;
            right: 0;
            display: flex;
            gap: 4px;
            background: var(--bg-surface);
            border: 1px solid var(--border-default);
            border-radius: 6px;
            padding: 4px;
            z-index: 100;
        }}

        .theme-toggle button {{
            font-family: 'Space Grotesk', sans-serif;
            font-size: 13px;
            font-weight: 500;
            padding: 6px 12px;
            border: none;
            border-radius: 4px;
            background: transparent;
            color: var(--text-muted);
            cursor: pointer;
            transition: all 0.2s ease;
        }}

        .theme-toggle button:hover {{
            color: var(--text-primary);
            background: var(--bg-elevated);
        }}

        .theme-toggle button.active {{
            background: var(--accent-primary);
            color: white;
        }}

        .resume-btn {{
            font-family: 'Space Grotesk', sans-serif;
            font-size: 14px;
            font-weight: 500;
            padding: 8px 16px;
            border: none;
            border-radius: 4px;
            background: var(--accent-primary);
            color: white;
            cursor: pointer;
            transition: all 0.2s ease;
            display: inline-flex;
            align-items: center;
            gap: 6px;
            margin-top: 12px;
        }}

        .resume-btn:hover {{
            background: var(--accent-secondary);
            transform: translateY(-1px);
        }}

        .resume-btn:active {{
            transform: translateY(0);
        }}

        .resume-btn.success {{
            background: var(--success);
        }}

        .resume-btn.error {{
            background: var(--danger);
        }}

        .tool-badge {{
            font-family: 'JetBrains Mono', 'Consolas', monospace;
            font-size: 11px;
            font-weight: 600;
            padding: 3px 8px;
            border-radius: 3px;
            background: var(--code-bg);
            color: var(--accent-primary);
            text-transform: uppercase;
            letter-spacing: 0.5px;
            display: inline-block;
            margin-bottom: 8px;
        }}

        .tool-badge.claude {{
            background: rgba(88, 166, 255, 0.15);
            color: var(--accent-primary);
        }}

        .tool-badge.vibe {{
            background: rgba(255, 149, 0, 0.15);
            color: var(--warning);
        }}

        .tool-badge.opencode {{
            background: rgba(46, 204, 113, 0.15);
            color: var(--success);
        }}
    </style>
</head>
<body>
    <!-- Theme Toggle -->
    <div class="theme-toggle">
        <button onclick="setTheme('light')" data-theme="light">Light</button>
        <button onclick="setTheme('system')" data-theme="system" class="active">System</button>
        <button onclick="setTheme('dark')" data-theme="dark">Dark</button>
    </div>

    <a href="/" class="back-button">← Back to Search</a>
    <div id="conversation"></div>
    
    <script>
        // Theme Management
        function setTheme(theme) {{
            localStorage.setItem('theme-preference', theme);
            applyTheme(theme);
            document.querySelectorAll('.theme-toggle button').forEach(btn => {{
                btn.classList.toggle('active', btn.dataset.theme === theme);
            }});
        }}

        function applyTheme(theme) {{
            const root = document.documentElement;
            if (theme === 'system') {{
                root.removeAttribute('data-theme');
            }} else {{
                root.setAttribute('data-theme', theme);
            }}
        }}

        function initTheme() {{
            const savedTheme = localStorage.getItem('theme-preference') || 'system';
            applyTheme(savedTheme);
            document.querySelectorAll('.theme-toggle button').forEach(btn => {{
                btn.classList.toggle('active', btn.dataset.theme === savedTheme);
            }});
        }}

        initTheme();

        async function loadConversation() {{
            const div = document.getElementById('conversation');

            try {{
                const response = await fetch('/api/conversation/{conversation_id}');

                if (!response.ok) {{
                    const errorData = await response.json().catch(() => ({{detail: 'Unknown error'}}));
                    throw new Error(errorData.detail || `HTTP ${{response.status}}`);
                }}

                const data = await response.json();

                // Validate data
                if (!data || typeof data !== 'object') {{
                    throw new Error('Invalid response data');
                }}

                const tool = data.tool || (data.file_path.endsWith('.jsonl') ? 'claude' : 'vibe');
                const toolLabel = tool === 'opencode' ? 'OpenCode' : (tool === 'vibe' ? 'Vibe' : 'Claude Code');
                const projectPath = data.project_path || '';
                const headerMeta = projectPath
                    ? `Project: ${{projectPath}}`
                    : `Project: ${{data.project_id || 'Unknown'}}`;

                div.innerHTML = `
                    <div class="header">
                        <span class="tool-badge ${{tool}}">${{toolLabel}}</span>
                        <h2>${{data.title || 'No title available'}}</h2>
                        <div>${{headerMeta}} | Messages: ${{data.message_count || 0}}</div>
                        <button class="resume-btn" id="resumeBtn" onclick="resumeSession('{conversation_id}', this)">
                            ⚡ Resume Session
                        </button>
                    </div>
                `;

                if (data.messages && Array.isArray(data.messages)) {{
                    data.messages.forEach((msg, i) => {{
                        const msgDiv = document.createElement('div');
                        msgDiv.className = `message ${{msg.role || 'unknown'}}`;
                        msgDiv.innerHTML = `
                            <div class="role">${{(msg.role || 'unknown').toUpperCase()}} - Message ${{i + 1}}</div>
                            <div class="content">${{(msg.content || '').substring(0, 2000)}}${{(msg.content || '').length > 2000 ? '...[truncated]' : ''}}</div>
                        `;
                        div.appendChild(msgDiv);
                    }});
                }} else {{
                    div.innerHTML += '<div class="message">No messages available</div>';
                }}
            }} catch (error) {{
                div.innerHTML = `
                    <div class="header" style="border-left-color: #f44336;">
                        <h2>Error Loading Conversation</h2>
                    </div>
                    <div class="message" style="border-left-color: #f44336;">
                        <div class="role">ERROR</div>
                        <div class="content">${{error.message}}</div>
                        <div class="content" style="margin-top: 10px; opacity: 0.7;">
                            Conversation ID: {conversation_id}
                        </div>
                    </div>
                `;
                console.error('Error loading conversation:', error);
            }}
        }}

        async function resumeSession(conversationId, buttonElement) {{
            const originalText = buttonElement.innerHTML;
            buttonElement.innerHTML = '⏳ Opening...';
            buttonElement.disabled = true;

            try {{
                const response = await fetch('/api/resume', {{
                    method: 'POST',
                    headers: {{ 'Content-Type': 'application/json' }},
                    body: JSON.stringify({{ conversation_id: conversationId }})
                }});

                const data = await response.json();

                if (response.ok && data.success) {{
                    buttonElement.innerHTML = '✓ Opened in terminal';
                    buttonElement.classList.add('success');
                    setTimeout(() => {{
                        buttonElement.innerHTML = originalText;
                        buttonElement.classList.remove('success');
                        buttonElement.disabled = false;
                    }}, 2000);
                }} else {{
                    throw new Error(data.detail || 'Failed to resume session');
                }}
            }} catch (error) {{
                buttonElement.innerHTML = '❌ Failed - check console';
                buttonElement.classList.add('error');
                console.error('Resume error:', error);
                setTimeout(() => {{
                    buttonElement.innerHTML = originalText;
                    buttonElement.classList.remove('error');
                    buttonElement.disabled = false;
                }}, 3000);
            }}
        }}

        loadConversation();
    </script>
</body>
</html>
    """)


def main():
    """Run the server with configurable host and port"""
    import uvicorn
    import socket
    import warnings

    warnings.filterwarnings(
        "ignore",
        message=r"resource_tracker: There appear to be .* leaked semaphore objects to clean up at shutdown",
        category=UserWarning,
    )

    # Get host from environment or use default
    host = os.getenv(ENV_HOST, DEFAULT_HOST)

    # Get port from environment or scan for available port
    env_port = os.getenv(ENV_PORT)
    if env_port:
        try:
            port = int(env_port)
            if not (1 <= port <= 65535):
                print(ERROR_INVALID_PORT.format(port=port))
                return
        except ValueError:
            print(ERROR_INVALID_PORT.format(port=env_port))
            return
    else:
        # Scan for available port in range
        port, max_port = PORT_SCAN_RANGE

        while port <= max_port:
            try:
                # Test if port is available
                with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                    s.bind((host, port))
                # Port is available
                break
            except OSError:
                port += 1

        if port > max_port:
            print(ERROR_PORT_IN_USE.format(
                start=PORT_SCAN_RANGE[0],
                end=PORT_SCAN_RANGE[1],
                port=port
            ))
            return

    print(f"Starting Claude Search server...")
    print(f"  URL: http://localhost:{port}")
    print(f"  Host: {host}")
    print(f"  Port: {port}")
    print()
    print("Press Ctrl+C to stop")

    uvicorn.run(app, host=host, port=port)


if __name__ == "__main__":
    main()
