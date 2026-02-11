"""Admin endpoints - server shutdown and watcher status."""
from __future__ import annotations

import os
import signal
import logging
from datetime import datetime

from fastapi import APIRouter, BackgroundTasks

from searchat.api.dependencies import (
    get_watcher,
    watcher_stats,
    indexing_state,
)


router = APIRouter()
logger = logging.getLogger(__name__)


@router.get("/watcher/status")
async def get_watcher_status():
    """Get live file watcher status."""
    watcher = get_watcher()

    return {
        "running": watcher.is_running if watcher else False,
        "watched_directories": [str(d) for d in watcher.get_watched_directories()] if watcher else [],
        "indexed_since_start": watcher_stats["indexed_count"],
        "last_update": watcher_stats["last_update"],
    }


@router.post("/shutdown")
async def shutdown_server(background_tasks: BackgroundTasks, force: bool = False):
    """Gracefully shutdown the server with safety checks."""
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
        """Shutdown function to run in background."""
        import time
        time.sleep(0.5)  # Give time for response to be sent

        if force and indexing_state["in_progress"]:
            logger.warning(f"FORCED shutdown during indexing operation: {indexing_state['operation']}")
        else:
            logger.info("Server shutdown requested via API")

        # Stop watcher if running
        watcher = get_watcher()
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
