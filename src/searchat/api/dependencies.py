"""Shared dependencies for FastAPI routes.

This module must stay lightweight: avoid importing heavy ML/search modules at
import time. Heavy resources are initialized lazily and/or in background warmup.
"""
from __future__ import annotations

import asyncio
import logging
import os
import time
from threading import Lock
from pathlib import Path
import re
from typing import TYPE_CHECKING

from searchat.services import BackupManager, PlatformManager
from searchat.config import Config, PathResolver
from searchat.api.readiness import get_readiness


logger = logging.getLogger(__name__)


if TYPE_CHECKING:
    from searchat.api.duckdb_store import DuckDBStore
    from searchat.core.search_engine import SearchEngine


# Global singletons (initialized on startup)
_config: Config | None = None
_search_dir: Path | None = None
_search_engine = None
_indexer = None
_backup_manager: BackupManager | None = None
_platform_manager: PlatformManager | None = None
_bookmarks_service = None
_saved_queries_service = None
_dashboards_service = None
_analytics_service = None
_watcher = None
_duckdb_store = None
_expertise_store = None
_knowledge_graph_store = None

# Snapshot-scoped caches (keyed by dataset root, i.e. backup directory path).
_duckdb_store_by_dir: dict[str, "DuckDBStore"] = {}
_search_engine_by_dir: dict[str, "SearchEngine"] = {}

_service_lock = Lock()
_warmup_task: asyncio.Task[None] | None = None


# Shared state
projects_cache = None
projects_summary_cache = None
stats_cache = None
watcher_stats = {"indexed_count": 0, "last_update": None}
indexing_state = {
    "in_progress": False,
    "operation": None,  # "manual_index" or "watcher"
    "started_at": None,
    "files_total": 0,
    "files_processed": 0
}


def initialize_services():
    """Initialize all services on app startup."""
    global _config, _search_dir, _backup_manager, _platform_manager, _bookmarks_service, _saved_queries_service, _dashboards_service, _analytics_service, _duckdb_store, _expertise_store, _knowledge_graph_store

    readiness = get_readiness()
    readiness.set_component("services", "loading")
    try:
        _config = Config.load()
        _search_dir = PathResolver.get_shared_search_dir(_config)
        _backup_manager = BackupManager(_search_dir)
        _platform_manager = PlatformManager()

        from searchat.api.duckdb_store import DuckDBStore
        from searchat.services.bookmarks import BookmarksService
        from searchat.services.saved_queries import SavedQueriesService
        from searchat.services.dashboards import DashboardsService
        from searchat.services.analytics import SearchAnalyticsService

        _duckdb_store = DuckDBStore(_search_dir, memory_limit_mb=_config.performance.memory_limit_mb)

        if _config.expertise.enabled:
            from searchat.expertise.store import ExpertiseStore
            _expertise_store = ExpertiseStore(_search_dir)
        if _config.knowledge_graph.enabled:
            from searchat.knowledge_graph import KnowledgeGraphStore
            _knowledge_graph_store = KnowledgeGraphStore(_search_dir)
        _bookmarks_service = BookmarksService(_config)
        _analytics_service = SearchAnalyticsService(_config)
        _saved_queries_service = SavedQueriesService(_config)
        _dashboards_service = DashboardsService(_config)
        readiness.set_component("services", "ready")
    except Exception as e:
        readiness.set_component("services", "error", error=str(e))
        raise


def start_background_warmup() -> None:
    """Kick off background warmup (non-blocking, idempotent)."""
    global _warmup_task

    if _config is None or _search_dir is None:
        return

    readiness = get_readiness()
    readiness.mark_warmup_started()

    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        # Not in an event loop; cannot schedule async task.
        return

    if _warmup_task is not None and not _warmup_task.done():
        return

    _warmup_task = loop.create_task(_warmup_all())


async def _warmup_all() -> None:
    """Warm up heavy components in the background."""
    # DuckDB parquet scan and embedded model download are independent — run concurrently.
    await asyncio.gather(
        asyncio.to_thread(_warmup_duckdb_parquet),
        asyncio.to_thread(_warmup_embedded_model),
    )
    # Search engine object (cheap), then semantic components that depend on it.
    await asyncio.to_thread(_ensure_search_engine)
    await asyncio.to_thread(_warmup_semantic_components)


def _warmup_embedded_model() -> None:
    """Ensure embedded GGUF model exists when embedded provider is enabled."""
    readiness = get_readiness()
    try:
        config = get_config()
    except Exception:
        return

    if config.llm.default_provider.lower() != "embedded":
        readiness.set_component("embedded_model", "idle")
        return

    from pathlib import Path

    from searchat.config.constants import DEFAULT_DATA_DIR
    from searchat.config.user_config_writer import ensure_user_settings_exists, update_llm_settings
    from searchat.llm.model_downloader import DownloadInProgressError, DownloadFailedError, download_file
    from searchat.llm.model_presets import get_preset

    readiness.set_component("embedded_model", "loading")
    try:
        configured = config.llm.embedded_model_path
        if configured:
            configured_path = Path(configured).expanduser()
            if configured_path.exists():
                readiness.set_component("embedded_model", "ready")
                return

        if not config.llm.embedded_auto_download:
            raise RuntimeError(
                "Embedded provider enabled but embedded_model_path is not set or missing. "
                "Set [llm].embedded_model_path or run 'searchat download-model --activate'."
            )

        preset = get_preset(config.llm.embedded_default_preset)
        dest_path = (DEFAULT_DATA_DIR / "models" / preset.filename).resolve()

        if not dest_path.exists():
            readiness.set_component(
                "embedded_model",
                "loading",
                error="Downloading embedded model (first run)...",
            )

            import time

            last_update = 0.0
            last_percent = -1

            def _progress(downloaded: int, total: int | None) -> None:
                nonlocal last_update, last_percent

                now = time.monotonic()
                if total is None or total <= 0:
                    if now - last_update < 0.5:
                        return
                    last_update = now
                    mb = downloaded / (1024 * 1024)
                    readiness.set_component(
                        "embedded_model",
                        "loading",
                        error=f"Downloading embedded model: {mb:.0f} MB...",
                    )
                    return

                percent = int((downloaded / total) * 100)
                if percent == last_percent and now - last_update < 0.5:
                    return
                last_percent = percent
                last_update = now
                mb_done = downloaded / (1024 * 1024)
                mb_total = total / (1024 * 1024)
                readiness.set_component(
                    "embedded_model",
                    "loading",
                    error=f"Downloading embedded model: {mb_done:.0f}/{mb_total:.0f} MB ({percent}%)",
                )

            download_file(url=preset.url, dest_path=dest_path, progress_cb=_progress)

        cfg_path = ensure_user_settings_exists(data_dir=DEFAULT_DATA_DIR)
        update_llm_settings(
            config_path=cfg_path,
            updates={
                "embedded_model_path": str(dest_path),
                "embedded_default_preset": preset.name,
                "embedded_auto_download": True,
            },
        )

        # Update in-memory config for this process.
        config.llm.embedded_model_path = str(dest_path)
        readiness.set_component("embedded_model", "ready")
    except DownloadInProgressError as exc:
        readiness.set_component("embedded_model", "loading", error=str(exc))
    except Exception as exc:
        readiness.set_component("embedded_model", "error", error=str(exc))


def _warmup_duckdb_parquet() -> None:
    readiness = get_readiness()
    started = time.perf_counter()
    try:
        readiness.set_component("duckdb", "loading")
        readiness.set_component("parquet", "loading")

        store = get_duckdb_store()
        store.validate_parquet_scan()

        readiness.set_component("duckdb", "ready")
        readiness.set_component("parquet", "ready")
    except Exception as e:
        msg = str(e)
        readiness.set_component("duckdb", "error", error=msg)
        readiness.set_component("parquet", "error", error=msg)
    finally:
        if os.getenv("SEARCHAT_PROFILE_WARMUP") == "1":
            elapsed_ms = (time.perf_counter() - started) * 1000.0
            logger.info("Warmup: duckdb/parquet %.1fms", elapsed_ms)


def _warmup_semantic_components() -> None:
    readiness = get_readiness()
    started = time.perf_counter()
    try:
        engine = _ensure_search_engine()

        readiness.set_component("metadata", "loading")
        engine.ensure_metadata_ready()
        readiness.set_component("metadata", "ready")

        readiness.set_component("faiss", "loading")
        engine.ensure_faiss_loaded()
        readiness.set_component("faiss", "ready")

        readiness.set_component(
            "embedder",
            "loading",
            error="Preparing embedding model (may download on first run)...",
        )
        engine.ensure_embedder_loaded()
        readiness.set_component("embedder", "ready")
    except Exception as e:
        msg = str(e)
        snap = readiness.snapshot()
        if snap.components.get("metadata") != "ready":
            readiness.set_component("metadata", "error", error=msg)
        if snap.components.get("faiss") != "ready":
            readiness.set_component("faiss", "error", error=msg)
        if snap.components.get("embedder") != "ready":
            readiness.set_component("embedder", "error", error=msg)
    finally:
        if os.getenv("SEARCHAT_PROFILE_WARMUP") == "1":
            elapsed_ms = (time.perf_counter() - started) * 1000.0
            logger.info("Warmup: semantic components %.1fms", elapsed_ms)


def get_or_create_search_engine():
    """Get search engine, creating it if needed (cheap)."""
    return _ensure_search_engine()


def invalidate_search_index() -> None:
    """Clear caches and mark semantic components stale after indexing."""
    global projects_cache, projects_summary_cache, stats_cache

    projects_cache = None
    projects_summary_cache = None
    stats_cache = None

    engine = _search_engine
    if engine is not None:
        engine.refresh_index()

    readiness = get_readiness()
    # Mark semantic components as not ready; warmup will rebuild.
    readiness.set_component("metadata", "idle")
    readiness.set_component("faiss", "idle")
    readiness.set_component("embedder", "idle")

    start_background_warmup()


def get_config() -> Config:
    """Get configuration singleton."""
    if _config is None:
        raise RuntimeError("Services not initialized. Call initialize_services() first.")
    return _config


def get_search_dir() -> Path:
    """Get search directory path."""
    if _search_dir is None:
        raise RuntimeError("Services not initialized. Call initialize_services() first.")
    return _search_dir


def get_duckdb_store():
    """Get DuckDBStore singleton."""
    if _duckdb_store is None:
        raise RuntimeError("Services not initialized. Call initialize_services() first.")
    return _duckdb_store


def _is_valid_snapshot_name(value: str) -> bool:
    if not value:
        return False
    if value in (".", ".."):
        return False
    if "/" in value or "\\" in value:
        return False
    if ".." in value:
        return False
    # Keep this conservative; backup folder names are ASCII-ish.
    return re.fullmatch(r"[A-Za-z0-9_.-]+", value) is not None


def resolve_dataset_search_dir(snapshot: str | None) -> tuple[Path, str | None]:
    """Resolve request dataset to a search_dir.

    Returns:
        (search_dir, snapshot_name)

    Raises:
        ValueError: If snapshot is invalid or does not exist.
    """
    if snapshot is None or snapshot == "":
        return get_search_dir(), None

    if not get_config().snapshots.enabled:
        raise ValueError("Snapshot mode is disabled")

    if not _is_valid_snapshot_name(snapshot):
        raise ValueError("Invalid snapshot name")

    backup_manager = get_backup_manager()
    backup_root = backup_manager.backup_dir.resolve()
    snapshot_dir = (backup_root / snapshot).resolve()
    if not snapshot_dir.is_relative_to(backup_root):
        raise ValueError("Invalid snapshot path")
    if not snapshot_dir.exists():
        raise ValueError("Snapshot not found")
    # Only allow snapshot browsing for backups that are explicitly marked as browsable.
    try:
        artifact = backup_manager.validate_backup_artifact(snapshot, verify_hashes=False)
    except AttributeError:
        artifact = {"snapshot_browsable": backup_manager.validate_backup(snapshot_dir)}
    if not artifact.get("snapshot_browsable"):
        raise ValueError("Snapshot validation failed")
    return snapshot_dir, snapshot


def get_duckdb_store_for(search_dir: Path) -> "DuckDBStore":
    """Get a DuckDBStore for a specific dataset root."""
    if search_dir == get_search_dir():
        return get_duckdb_store()

    key = str(search_dir)
    store = _duckdb_store_by_dir.get(key)
    if store is not None:
        return store

    config = get_config()
    from searchat.api.duckdb_store import DuckDBStore

    store = DuckDBStore(search_dir, memory_limit_mb=config.performance.memory_limit_mb)
    _duckdb_store_by_dir[key] = store
    return store


def get_or_create_search_engine_for(search_dir: Path) -> "SearchEngine":
    """Get (or create) a SearchEngine for a specific dataset root.

    Snapshot engines must not mutate readiness/warmup globals.
    """
    if search_dir == get_search_dir():
        return get_or_create_search_engine()

    key = str(search_dir)
    engine = _search_engine_by_dir.get(key)
    if engine is not None:
        return engine

    from searchat.core.search_engine import SearchEngine

    engine = SearchEngine(search_dir, get_config())
    _search_engine_by_dir[key] = engine
    return engine


def get_search_engine():
    """Get search engine singleton."""
    if _config is None or _search_dir is None:
        raise RuntimeError("Services not initialized. Call initialize_services() first.")
    engine = _search_engine
    if engine is None:
        raise RuntimeError("Search engine not ready")
    return engine


def get_indexer():
    """Get indexer singleton."""
    if _config is None or _search_dir is None:
        raise RuntimeError("Services not initialized. Call initialize_services() first.")
    idx = _indexer
    if idx is None:
        # Indexer is created lazily on first use.
        idx = _ensure_indexer()
    return idx


def get_backup_manager() -> BackupManager:
    """Get backup manager singleton."""
    if _backup_manager is None:
        raise RuntimeError("Services not initialized. Call initialize_services() first.")
    return _backup_manager


def get_platform_manager() -> PlatformManager:
    """Get platform manager singleton."""
    if _platform_manager is None:
        raise RuntimeError("Services not initialized. Call initialize_services() first.")
    return _platform_manager


def get_expertise_store():
    """Get expertise store singleton."""
    if _expertise_store is None:
        raise RuntimeError("Expertise store not initialized. Check expertise.enabled in config.")
    return _expertise_store


def get_knowledge_graph_store():
    """Get knowledge graph store singleton."""
    if _knowledge_graph_store is None:
        raise RuntimeError("Knowledge graph store not initialized. Check knowledge_graph.enabled in config.")
    return _knowledge_graph_store


def get_bookmarks_service():
    """Get bookmarks service singleton."""
    if _bookmarks_service is None:
        raise RuntimeError("Services not initialized. Call initialize_services() first.")
    return _bookmarks_service


def get_saved_queries_service():
    """Get saved queries service singleton."""
    if _saved_queries_service is None:
        raise RuntimeError("Services not initialized. Call initialize_services() first.")
    return _saved_queries_service


def get_dashboards_service():
    """Get dashboards service singleton."""
    if _dashboards_service is None:
        raise RuntimeError("Services not initialized. Call initialize_services() first.")
    return _dashboards_service


def get_analytics_service():
    """Get analytics service singleton."""
    if _analytics_service is None:
        raise RuntimeError("Services not initialized. Call initialize_services() first.")
    return _analytics_service


def get_watcher():
    """Get watcher singleton (may be None if not started)."""
    return _watcher


def set_watcher(watcher):
    """Set watcher singleton."""
    global _watcher
    _watcher = watcher


def _ensure_search_engine():
    """Create and initialize search engine (blocking)."""
    global _search_engine
    readiness = get_readiness()

    if _config is None or _search_dir is None:
        raise RuntimeError("Services not initialized")

    with _service_lock:
        if _search_engine is not None:
            return _search_engine

        readiness.set_component("search_engine", "loading")
        try:
            from searchat.core.search_engine import SearchEngine

            _search_engine = SearchEngine(_search_dir, _config)
            readiness.set_component("search_engine", "ready")
        except Exception as e:
            readiness.set_component("search_engine", "error", error=str(e))
            raise
        return _search_engine


def _ensure_indexer():
    """Create indexer lazily (blocking)."""
    global _indexer
    readiness = get_readiness()

    if _config is None or _search_dir is None:
        raise RuntimeError("Services not initialized")

    with _service_lock:
        if _indexer is not None:
            return _indexer

        readiness.set_component("indexer", "loading")
        try:
            from searchat.core.indexer import ConversationIndexer

            _indexer = ConversationIndexer(_search_dir, _config)
            readiness.set_component("indexer", "ready")
        except Exception as e:
            readiness.set_component("indexer", "error", error=str(e))
            raise
        return _indexer


def trigger_search_engine_warmup() -> None:
    """Ensure warmup is scheduled and search engine initialization is triggered."""
    start_background_warmup()
