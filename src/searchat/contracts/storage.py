"""StorageBackend protocol — abstraction seam for dataset access."""
from __future__ import annotations

from datetime import datetime
from typing import Protocol


class StorageBackend(Protocol):
    """Structural contract for dataset storage access.

    V1 methods map to the current DuckDBStore (Parquet-backed).
    V2 stubs will be implemented by the DuckDB-native backend in Phase 1.
    """

    # -- V1: current DuckDBStore methods --

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
