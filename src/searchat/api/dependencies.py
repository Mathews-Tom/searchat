"""
Shared dependencies for FastAPI routes.
Singleton pattern for heavy resources (search engine, indexer, embedder).
"""
from typing import Optional
from pathlib import Path

from searchat.core import SearchEngine, ConversationIndexer, ConversationWatcher
from searchat.services import BackupManager, PlatformManager
from searchat.config import Config, PathResolver


# Global singletons (initialized on startup)
_config: Optional[Config] = None
_search_dir: Optional[Path] = None
_search_engine: Optional[SearchEngine] = None
_indexer: Optional[ConversationIndexer] = None
_backup_manager: Optional[BackupManager] = None
_platform_manager: Optional[PlatformManager] = None
_watcher: Optional[ConversationWatcher] = None


# Shared state
projects_cache = None
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
    global _config, _search_dir, _search_engine, _indexer, _backup_manager, _platform_manager

    _config = Config.load()
    _search_dir = PathResolver.get_shared_search_dir(_config)
    _search_engine = SearchEngine(_search_dir, _config)
    _indexer = ConversationIndexer(_search_dir, _config)
    _backup_manager = BackupManager(_search_dir)
    _platform_manager = PlatformManager()


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


def get_search_engine() -> SearchEngine:
    """Get search engine singleton."""
    if _search_engine is None:
        raise RuntimeError("Services not initialized. Call initialize_services() first.")
    return _search_engine


def get_indexer() -> ConversationIndexer:
    """Get indexer singleton."""
    if _indexer is None:
        raise RuntimeError("Services not initialized. Call initialize_services() first.")
    return _indexer


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


def get_watcher() -> Optional[ConversationWatcher]:
    """Get watcher singleton (may be None if not started)."""
    return _watcher


def set_watcher(watcher: Optional[ConversationWatcher]):
    """Set watcher singleton."""
    global _watcher
    _watcher = watcher
