"""Mutable API runtime state kept separate from service composition."""

from __future__ import annotations

import asyncio
from typing import Any

projects_cache: list[str] | None = None
projects_summary_cache: list[dict[str, Any]] | None = None
stats_cache: dict[str, Any] | None = None

watcher_stats: dict[str, Any] = {
    "indexed_count": 0,
    "last_update": None,
}

indexing_state: dict[str, Any] = {
    "in_progress": False,
    "operation": None,
    "started_at": None,
    "files_total": 0,
    "files_processed": 0,
}

warmup_task: asyncio.Task[None] | None = None


def clear_query_caches() -> None:
    """Clear active-dataset caches populated by API routes."""
    global projects_cache, projects_summary_cache, stats_cache

    projects_cache = None
    projects_summary_cache = None
    stats_cache = None


def reset_runtime_state() -> None:
    """Reset mutable runtime state for tests and process startup."""
    global warmup_task

    clear_query_caches()
    watcher_stats["indexed_count"] = 0
    watcher_stats["last_update"] = None
    indexing_state.update(
        {
            "in_progress": False,
            "operation": None,
            "started_at": None,
            "files_total": 0,
            "files_processed": 0,
        }
    )
    warmup_task = None
