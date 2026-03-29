"""Dual-write proxy — writes to both Parquet+FAISS and DuckDB backends.

.. deprecated::
    The dual-writer is bypassed by :class:`searchat.core.unified_indexer.UnifiedIndexer`
    which writes directly to DuckDB. Retained for backward compatibility and emergency
    rollback. Will be removed in Phase 7 cleanup.

All reads are served from the Parquet backend (unchanged behavior).
Writes are forwarded to both backends. DuckDB write failures are logged
but do not fail the overall operation — the Parquet path remains the
source of truth until the read path is cut over in Phase 3.
"""
from __future__ import annotations

import logging
from datetime import datetime

from searchat.storage.unified_storage import UnifiedStorage

log = logging.getLogger(__name__)


class DualWriter:
    """Proxy that writes to both Parquet+FAISS and DuckDB.

    Implements the StorageBackend protocol by delegating all reads
    to the existing DuckDBStore (Parquet-backed) and forwarding
    writes to both backends.
    """

    def __init__(
        self,
        parquet_backend: object,
        duckdb_backend: UnifiedStorage,
    ) -> None:
        self._parquet = parquet_backend
        self._duckdb = duckdb_backend

    @property
    def parquet_backend(self) -> object:
        return self._parquet

    @property
    def duckdb_backend(self) -> UnifiedStorage:
        return self._duckdb

    # ------------------------------------------------------------------
    # StorageBackend protocol — reads delegate to Parquet
    # ------------------------------------------------------------------

    def list_projects(self) -> list[str]:
        return self._parquet.list_projects()  # type: ignore[union-attr]

    def list_project_summaries(self) -> list[dict]:
        return self._parquet.list_project_summaries()  # type: ignore[union-attr]

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
    ) -> list[dict]:
        return self._parquet.list_conversations(  # type: ignore[union-attr]
            sort_by=sort_by,
            project_id=project_id,
            date_from=date_from,
            date_to=date_to,
            tool=tool,
            limit=limit,
            offset=offset,
        )

    def count_conversations(
        self,
        *,
        project_id: str | None = None,
        date_from: datetime | None = None,
        date_to: datetime | None = None,
        tool: str | None = None,
    ) -> int:
        return self._parquet.count_conversations(  # type: ignore[union-attr]
            project_id=project_id,
            date_from=date_from,
            date_to=date_to,
            tool=tool,
        )

    def validate_parquet_scan(self) -> None:
        self._parquet.validate_parquet_scan()  # type: ignore[union-attr]

    def get_conversation_meta(self, conversation_id: str) -> dict | None:
        return self._parquet.get_conversation_meta(conversation_id)  # type: ignore[union-attr]

    def get_conversation_record(self, conversation_id: str) -> dict | None:
        return self._parquet.get_conversation_record(conversation_id)  # type: ignore[union-attr]

    def get_statistics(self):
        return self._parquet.get_statistics()  # type: ignore[union-attr]

    # ------------------------------------------------------------------
    # Write operations — forward to both backends
    # ------------------------------------------------------------------

    def write_conversation(
        self,
        *,
        conversation_id: str,
        project_id: str,
        file_path: str,
        title: str,
        created_at: datetime,
        updated_at: datetime,
        message_count: int,
        full_text: str,
        file_hash: str,
        indexed_at: datetime,
        messages: list[dict] | None = None,
        files_mentioned: list[str] | None = None,
        git_branch: str | None = None,
    ) -> None:
        """Write a conversation to the DuckDB backend.

        The Parquet backend is written to by the existing indexer
        pipeline — the DualWriter only adds the DuckDB side.
        """
        try:
            self._duckdb.upsert_conversation(
                conversation_id=conversation_id,
                project_id=project_id,
                file_path=file_path,
                title=title,
                created_at=created_at,
                updated_at=updated_at,
                message_count=message_count,
                full_text=full_text,
                file_hash=file_hash,
                indexed_at=indexed_at,
                files_mentioned=files_mentioned,
                git_branch=git_branch,
            )
            if messages:
                self._duckdb.insert_messages(conversation_id, messages)
        except Exception:
            log.exception(
                "DuckDB dual-write failed for conversation %s",
                conversation_id,
            )

    def write_file_state(
        self,
        *,
        file_path: str,
        conversation_id: str | None = None,
        project_id: str | None = None,
        connector_name: str | None = None,
        file_size: int = 0,
        file_hash: str | None = None,
    ) -> None:
        """Write file state to the DuckDB backend."""
        try:
            self._duckdb.upsert_file_state(
                file_path=file_path,
                conversation_id=conversation_id,
                project_id=project_id,
                connector_name=connector_name,
                file_size=file_size,
                file_hash=file_hash,
            )
        except Exception:
            log.exception(
                "DuckDB dual-write failed for file_state %s", file_path,
            )

    def write_code_block(self, **kwargs) -> None:
        """Write a code block to the DuckDB backend."""
        try:
            self._duckdb.insert_code_block(**kwargs)
        except Exception:
            log.exception("DuckDB dual-write failed for code_block")
