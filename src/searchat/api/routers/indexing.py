"""Indexing endpoints - manual reindex and index missing conversations."""
import logging
import time
from datetime import datetime

from fastapi import APIRouter, HTTPException

from searchat.config import PathResolver
from searchat.api.dependencies import (
    get_config,
    get_indexer,
    get_search_engine,
    projects_cache,
    indexing_state,
)


router = APIRouter()
logger = logging.getLogger(__name__)


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
async def index_missing():
    """Index conversations that aren't already indexed (append-only, safe)."""
    global projects_cache, indexing_state

    try:
        start_time = time.time()
        config = get_config()
        indexer = get_indexer()
        search_engine = get_search_engine()

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
        search_engine._initialize()

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
