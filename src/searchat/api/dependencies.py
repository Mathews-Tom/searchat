"""Shared dependencies for FastAPI routes.

This module must stay lightweight: avoid importing heavy ML/search modules at
import time. Heavy resources are initialized lazily and/or in background warmup.
"""

from __future__ import annotations

import logging
from threading import Lock
from pathlib import Path
import re
from typing import TYPE_CHECKING

from searchat.contracts.errors import snapshot_mode_disabled_message
from searchat.services import BackupManager, PlatformManager
from searchat.config import Config, PathResolver
from searchat.api.readiness import get_readiness

logger = logging.getLogger(__name__)


if TYPE_CHECKING:
    from searchat.contracts import RetrievalBackend, StorageBackend


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
_palace_query = None

# Snapshot-scoped caches (keyed by dataset root, i.e. backup directory path).
_duckdb_store_by_dir: dict[str, "StorageBackend"] = {}
_search_engine_by_dir: dict[str, "RetrievalBackend"] = {}

_service_lock = Lock()


def initialize_services():
    """Initialize all services on app startup."""
    global \
        _config, \
        _search_dir, \
        _backup_manager, \
        _platform_manager, \
        _bookmarks_service, \
        _saved_queries_service, \
        _dashboards_service, \
        _analytics_service, \
        _duckdb_store, \
        _expertise_store, \
        _knowledge_graph_store

    readiness = get_readiness()
    readiness.set_component("services", "loading")
    try:
        _config = Config.load()
        _search_dir = PathResolver.get_shared_search_dir(_config)
        _backup_manager = BackupManager(_search_dir)
        _platform_manager = PlatformManager()

        from searchat.services.bookmarks import BookmarksService
        from searchat.services.saved_queries import SavedQueriesService
        from searchat.services.dashboards import DashboardsService
        from searchat.services.analytics import SearchAnalyticsService
        from searchat.services.storage_service import build_storage_service

        _duckdb_store = build_storage_service(
            _search_dir,
            config=_config,
            read_only=False,
        )

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
    from searchat.api import warmup as api_warmup

    api_warmup.start_background_warmup()


async def _warmup_all() -> None:
    """Warm up heavy components in the background."""
    from searchat.api import warmup as api_warmup

    await api_warmup._warmup_all()


def _warmup_embedded_model() -> None:
    """Ensure embedded GGUF model exists when embedded provider is enabled."""
    from searchat.api import warmup as api_warmup

    api_warmup._warmup_embedded_model()


def _warmup_duckdb_parquet() -> None:
    from searchat.api import warmup as api_warmup

    api_warmup._warmup_duckdb_parquet()


def _warmup_semantic_components() -> None:
    from searchat.api import warmup as api_warmup

    api_warmup._warmup_semantic_components()


def get_or_create_search_engine():
    """Get search engine, creating it if needed (cheap)."""
    return _ensure_search_engine()


def invalidate_search_index() -> None:
    """Clear caches and mark semantic components stale after indexing."""
    from searchat.api import warmup as api_warmup

    api_warmup.invalidate_search_index()


def get_config() -> Config:
    """Get configuration singleton."""
    if _config is None:
        raise RuntimeError(
            "Services not initialized. Call initialize_services() first."
        )
    return _config


def get_search_dir() -> Path:
    """Get search directory path."""
    if _search_dir is None:
        raise RuntimeError(
            "Services not initialized. Call initialize_services() first."
        )
    return _search_dir


def get_duckdb_store():
    """Get DuckDBStore singleton."""
    if _duckdb_store is None:
        raise RuntimeError(
            "Services not initialized. Call initialize_services() first."
        )
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
        raise ValueError(snapshot_mode_disabled_message())

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
        artifact = backup_manager.validate_backup_artifact(
            snapshot, verify_hashes=False
        )
    except AttributeError:
        artifact = {"snapshot_browsable": backup_manager.validate_backup(snapshot_dir)}
    if not artifact.get("snapshot_browsable"):
        raise ValueError("Snapshot validation failed")
    return snapshot_dir, snapshot


def get_duckdb_store_for(search_dir: Path) -> "StorageBackend":
    """Get a storage service for a specific dataset root."""
    if search_dir == get_search_dir():
        return get_duckdb_store()

    key = str(search_dir)
    store = _duckdb_store_by_dir.get(key)
    if store is not None:
        return store

    config = get_config()
    from searchat.services.storage_service import build_storage_service

    store = build_storage_service(search_dir, config=config)
    _duckdb_store_by_dir[key] = store
    return store


def get_or_create_search_engine_for(search_dir: Path) -> "RetrievalBackend":
    """Get (or create) a SearchEngine for a specific dataset root.

    Snapshot engines must not mutate readiness/warmup globals.
    """
    if search_dir == get_search_dir():
        return get_or_create_search_engine()

    key = str(search_dir)
    engine = _search_engine_by_dir.get(key)
    if engine is not None:
        return engine

    from searchat.services.retrieval_service import build_retrieval_service

    engine = build_retrieval_service(search_dir, config=get_config())
    _search_engine_by_dir[key] = engine
    return engine


def get_search_engine():
    """Get search engine singleton."""
    if _config is None or _search_dir is None:
        raise RuntimeError(
            "Services not initialized. Call initialize_services() first."
        )
    engine = _search_engine
    if engine is None:
        raise RuntimeError("Search engine not ready")
    return engine


def get_indexer():
    """Get indexer singleton."""
    if _config is None or _search_dir is None:
        raise RuntimeError(
            "Services not initialized. Call initialize_services() first."
        )
    idx = _indexer
    if idx is None:
        # Indexer is created lazily on first use.
        idx = _ensure_indexer()
    return idx


def get_backup_manager() -> BackupManager:
    """Get backup manager singleton."""
    if _backup_manager is None:
        raise RuntimeError(
            "Services not initialized. Call initialize_services() first."
        )
    return _backup_manager


def get_platform_manager() -> PlatformManager:
    """Get platform manager singleton."""
    if _platform_manager is None:
        raise RuntimeError(
            "Services not initialized. Call initialize_services() first."
        )
    return _platform_manager


def get_expertise_store():
    """Get expertise store singleton."""
    if _expertise_store is None:
        raise RuntimeError(
            "Expertise store not initialized. Check expertise.enabled in config."
        )
    return _expertise_store


def get_knowledge_graph_store():
    """Get knowledge graph store singleton."""
    if _knowledge_graph_store is None:
        raise RuntimeError(
            "Knowledge graph store not initialized. Check knowledge_graph.enabled in config."
        )
    return _knowledge_graph_store


def get_palace_query():
    """Get palace query singleton (lazy-initialized)."""
    global _palace_query
    if _palace_query is not None:
        return _palace_query

    config = get_config()
    if not config.palace.enabled:
        raise RuntimeError(
            "Palace is not enabled. Set palace.enabled = true in config."
        )

    search_dir = get_search_dir()
    with _service_lock:
        if _palace_query is not None:
            return _palace_query

        from searchat.palace.query import PalaceQuery

        data_dir = search_dir / "data"
        _palace_query = PalaceQuery(data_dir=data_dir, config=config)
        return _palace_query


def get_bookmarks_service():
    """Get bookmarks service singleton."""
    if _bookmarks_service is None:
        raise RuntimeError(
            "Services not initialized. Call initialize_services() first."
        )
    return _bookmarks_service


def get_saved_queries_service():
    """Get saved queries service singleton."""
    if _saved_queries_service is None:
        raise RuntimeError(
            "Services not initialized. Call initialize_services() first."
        )
    return _saved_queries_service


def get_dashboards_service():
    """Get dashboards service singleton."""
    if _dashboards_service is None:
        raise RuntimeError(
            "Services not initialized. Call initialize_services() first."
        )
    return _dashboards_service


def get_analytics_service():
    """Get analytics service singleton."""
    if _analytics_service is None:
        raise RuntimeError(
            "Services not initialized. Call initialize_services() first."
        )
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
            from searchat.services.retrieval_service import build_retrieval_service

            _search_engine = build_retrieval_service(_search_dir, config=_config)
            readiness.set_component("search_engine", "ready")
        except Exception as e:
            readiness.set_component("search_engine", "error", error=str(e))
            raise
        return _search_engine


def _ensure_indexer():
    """Create indexer lazily (blocking).

    Returns UnifiedIndexer (DuckDB-native) which bypasses the dual-writer
    and writes directly to DuckDB with exchange-level segmentation.
    """
    global _indexer
    readiness = get_readiness()

    if _config is None or _search_dir is None:
        raise RuntimeError("Services not initialized")

    with _service_lock:
        if _indexer is not None:
            return _indexer

        readiness.set_component("indexer", "loading")
        try:
            from searchat.core.unified_indexer import UnifiedIndexer

            _indexer = UnifiedIndexer(
                _search_dir,
                _config,
                storage=get_duckdb_store(),
            )
            readiness.set_component("indexer", "ready")
        except Exception as e:
            readiness.set_component("indexer", "error", error=str(e))
            raise
        return _indexer


def trigger_search_engine_warmup() -> None:
    """Ensure warmup is scheduled and search engine initialization is triggered."""
    from searchat.api import warmup as api_warmup

    api_warmup.trigger_search_engine_warmup()
