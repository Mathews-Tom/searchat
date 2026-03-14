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
    """Create the storage service for a dataset root."""
    from searchat.services.duckdb_storage import DuckDBStore

    return DuckDBStore(search_dir, memory_limit_mb=config.performance.memory_limit_mb)
