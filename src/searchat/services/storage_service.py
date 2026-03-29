"""Storage-facing service contract and construction helpers."""
from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Protocol

from searchat.config import Config


class StorageService(Protocol):
    """Minimal dataset access contract used by API, CLI, and integrations."""

    def list_projects(self) -> list[str]: ...

    def list_project_summaries(self) -> list[dict]: ...

    def list_conversations(
        self,
        *,
        sort_by: str = "length",
        project_id: str | None = None,
        date_from: datetime | None = None,
        date_to: datetime | None = None,
        tool: str | None = None,
        limit: int | None = None,
        offset: int = 0,
    ) -> list[dict]: ...

    def count_conversations(
        self,
        *,
        project_id: str | None = None,
        date_from: datetime | None = None,
        date_to: datetime | None = None,
        tool: str | None = None,
    ) -> int: ...

    def validate_parquet_scan(self) -> None: ...

    def get_conversation_meta(self, conversation_id: str) -> dict | None: ...

    def get_conversation_record(self, conversation_id: str) -> dict | None: ...

    def get_statistics(self): ...


def build_storage_service(search_dir: Path, *, config: Config) -> StorageService:
    """Create the storage service for a dataset root.

    Returns UnifiedStorage (DuckDB-native) backed by the persistent DuckDB file.
    Creates the database if it does not exist yet.
    """
    from searchat.storage.unified_storage import UnifiedStorage

    db_path = config.storage.resolve_duckdb_path(search_dir)
    read_only = db_path.exists()
    return UnifiedStorage(
        db_path,
        memory_limit_mb=config.performance.memory_limit_mb,
        hnsw_ef_construction=config.storage.hnsw_ef_construction,
        hnsw_ef_search=config.storage.hnsw_ef_search,
        hnsw_m=config.storage.hnsw_m,
        read_only=read_only,
    )
