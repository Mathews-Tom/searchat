"""Indexing endpoints - manual reindex and index missing conversations."""

from __future__ import annotations

import asyncio
import time
from datetime import datetime

from fastapi import APIRouter, HTTPException, Query

from searchat.core.logging_config import get_logger
from searchat.core.progress import LoggingProgressAdapter
from searchat.core.connectors import get_connectors
import searchat.api.dependencies as deps

from searchat.api.dependencies import (
    get_config,
    get_indexer,
    indexing_state,
    invalidate_search_index,
)


router = APIRouter()
logger = get_logger(__name__)


class StateTrackingProgressAdapter(LoggingProgressAdapter):
    """Progress adapter that updates API indexing state."""

    def __init__(self, state_dict: dict) -> None:
        super().__init__()
        self.state = state_dict

    def update_file_progress(self, current: int, total: int, filename: str) -> None:
        """Update file progress and API state."""
        super().update_file_progress(current, total, filename)
        self.state["files_processed"] = current
        self.state["files_total"] = total


@router.post("/reindex")
async def reindex():
    """Rebuild the search index - DISABLED FOR DATA SAFETY."""
    # SAFETY GUARD: Block all reindexing to protect irreplaceable conversation data
    raise HTTPException(
        status_code=403,
        detail="BLOCKED: Reindexing disabled to protect irreplaceable conversation data. "
               "Source JSONLs are missing - rebuilding would cause data loss."
    )


@router.post("/index_missing")
async def index_missing(snapshot: str | None = Query(None, description="Backup snapshot name (read-only)")):
    """Index conversations that aren't already indexed (append-only, safe)."""
    if snapshot is not None:
        raise HTTPException(status_code=403, detail="Indexing is disabled in snapshot mode")
    global projects_cache, indexing_state

    try:
        start_time = time.time()
        config = get_config()
        indexer = get_indexer()

        # Get all conversation files
        all_files: list[str] = []
        for connector in get_connectors():
            try:
                for path in connector.discover_files(config):
                    all_files.append(str(path))
            except Exception as exc:
                logger.warning("Error scanning %s: %s", getattr(connector, "name", "<unknown>"), exc)

        # Get already indexed files
        indexed_paths = indexer.get_indexed_file_paths()

        # Find new files
        new_files = [f for f in all_files if f not in indexed_paths]
        already_indexed_count = len(all_files) - len(new_files)

        if not new_files:
            logger.info(f"No missing conversations found. Total: {len(all_files)}, Already indexed: {already_indexed_count}")
            return {
                "success": True,
                "new_conversations": 0,
                "failed_conversations": 0,
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

        # Create progress adapter that updates state
        progress = StateTrackingProgressAdapter(indexing_state)

        # Index new files (run in thread pool to avoid blocking)
        logger.info(f"Indexing {len(new_files)} missing conversations")
        stats = await asyncio.to_thread(
            indexer.index_append_only,
            new_files,
            progress,
        )

        invalidate_search_index()

        elapsed_time = time.time() - start_time
        failed_count = stats.skipped_conversations

        if failed_count > 0:
            message = f"Added {stats.new_conversations} conversations, {failed_count} failed (see errors above)"
            logger.warning(f"Indexing complete: {stats.new_conversations} added, {failed_count} failed (see errors above)")
        else:
            message = f"Added {stats.new_conversations} conversations to index"
            logger.info(f"Indexing complete: {stats.new_conversations} added successfully")

        result = {
            "success": True,
            "new_conversations": stats.new_conversations,
            "failed_conversations": failed_count,
            "total_files": len(all_files),
            "already_indexed": len(indexed_paths),
            "time_seconds": round(elapsed_time, 2),
            "message": message
        }

        return result

    except Exception as e:
        logger.error(f"Error indexing missing conversations: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        # Mark indexing complete
        indexing_state["in_progress"] = False
        indexing_state["operation"] = None
