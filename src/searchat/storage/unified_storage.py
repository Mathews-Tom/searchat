"""DuckDB-native unified storage — implements StorageBackend protocol.

Replaces per-query in-memory DuckDB connections with a persistent file
that owns conversations, messages, exchanges, embeddings, file state,
and code blocks. Thread safety: one shared connection, fresh cursors
per read, thread-local cursors for writes.
"""

from __future__ import annotations

import logging
import threading
from datetime import datetime
from pathlib import Path

from dataclasses import dataclass

import duckdb

from searchat.storage.schema import (
    EMBEDDING_DIM,
    create_hnsw_indexes,
    ensure_tables,
    install_fts,
    install_vss,
    table_row_counts,
)

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class IndexStatistics:
    total_conversations: int
    total_messages: int
    avg_messages: float
    total_projects: int
    earliest_date: str | None
    latest_date: str | None


class UnifiedStorage:
    """DuckDB-backed storage implementing the StorageBackend protocol."""

    def __init__(
        self,
        db_path: str | Path,
        *,
        memory_limit_mb: int | None = None,
        hnsw_ef_construction: int = 128,
        hnsw_ef_search: int = 64,
        hnsw_m: int = 16,
        read_only: bool = False,
    ) -> None:
        self._db_path = Path(db_path)
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._read_only = read_only
        self._memory_limit_mb = memory_limit_mb
        self._hnsw_ef_construction = hnsw_ef_construction
        self._hnsw_ef_search = hnsw_ef_search
        self._hnsw_m = hnsw_m

        self._conn = duckdb.connect(
            str(self._db_path),
            read_only=read_only,
        )
        if memory_limit_mb is not None:
            self._conn.execute(f"PRAGMA memory_limit='{int(memory_limit_mb)}MB'")

        # Thread-local storage for write cursors
        self._local = threading.local()

        # Initialize extensions
        self._vss_available = install_vss(self._conn)
        self._fts_available = install_fts(self._conn)

        if not read_only:
            ensure_tables(self._conn)

        if self._vss_available and not read_only:
            # Enable HNSW persistence for on-disk databases
            try:
                self._conn.execute("SET hnsw_enable_experimental_persistence = true")
            except duckdb.Error:
                pass
            create_hnsw_indexes(
                self._conn,
                ef_construction=hnsw_ef_construction,
                m=hnsw_m,
            )

    @property
    def connection(self) -> duckdb.DuckDBPyConnection:
        return self._conn

    def close(self) -> None:
        self._conn.close()

    # ------------------------------------------------------------------
    # Cursor management
    # ------------------------------------------------------------------

    def _connect(self) -> duckdb.DuckDBPyConnection:
        """Create an in-memory DuckDB connection for ad-hoc Parquet queries.

        Used by API routes that scan Parquet files directly (code blocks,
        expertise, etc.) via ``parquet_scan()``.
        """
        con = duckdb.connect(database=":memory:")
        if self._memory_limit_mb is not None:
            con.execute(f"PRAGMA memory_limit='{int(self._memory_limit_mb)}MB'")
        return con

    def _read_cursor(self) -> duckdb.DuckDBPyConnection:
        """Fresh cursor for read operations (concurrent-safe)."""
        return self._conn.cursor()

    def _write_cursor(self) -> duckdb.DuckDBPyConnection:
        """Thread-local cursor for write operations."""
        cursor = getattr(self._local, "write_cursor", None)
        if cursor is None:
            cursor = self._conn.cursor()
            self._local.write_cursor = cursor
        return cursor

    # ------------------------------------------------------------------
    # StorageBackend protocol — V1 read methods
    # ------------------------------------------------------------------

    def list_projects(self) -> list[str]:
        cur = self._read_cursor()
        try:
            rows = cur.execute(
                "SELECT DISTINCT project_id FROM conversations "
                "WHERE message_count > 0 ORDER BY project_id"
            ).fetchall()
            return [r[0] for r in rows]
        finally:
            cur.close()

    def list_project_summaries(self) -> list[dict]:
        cur = self._read_cursor()
        try:
            rows = cur.execute(
                "SELECT project_id, "
                "  COUNT(*)::BIGINT AS conversation_count, "
                "  COALESCE(SUM(message_count), 0)::BIGINT AS message_count, "
                "  MAX(updated_at) AS updated_at "
                "FROM conversations WHERE message_count > 0 "
                "GROUP BY project_id ORDER BY project_id"
            ).fetchall()
            return [
                {
                    "project_id": pid,
                    "conversation_count": int(cc),
                    "message_count": int(mc),
                    "updated_at": ua.isoformat()
                    if isinstance(ua, datetime)
                    else str(ua),
                }
                for pid, cc, mc, ua in rows
            ]
        finally:
            cur.close()

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
        order_by = {
            "length": "message_count DESC",
            "date_newest": "updated_at DESC",
            "date_oldest": "updated_at ASC",
            "title": "title ASC",
        }.get(sort_by, "message_count DESC")

        conditions = ["message_count > 0"]
        params: list[object] = []

        if project_id:
            conditions.append("project_id = ?")
            params.append(project_id)
        if date_from:
            conditions.append("updated_at >= ?")
            params.append(date_from)
        if date_to:
            conditions.append("updated_at < ?")
            params.append(date_to)
        if tool:
            conditions.append("file_path LIKE ?")
            params.append(f"%{tool}%")

        where = " AND ".join(conditions)
        query = (
            f"SELECT conversation_id, project_id, title, created_at, "
            f"updated_at, message_count, file_path, full_text "
            f"FROM conversations WHERE {where} ORDER BY {order_by}"
        )
        if limit is not None:
            query += " LIMIT ? OFFSET ?"
            params.extend([int(limit), int(offset)])

        cur = self._read_cursor()
        try:
            rows = cur.execute(query, params).fetchall()
            columns = [
                "conversation_id",
                "project_id",
                "title",
                "created_at",
                "updated_at",
                "message_count",
                "file_path",
                "full_text",
            ]
            return [dict(zip(columns, row)) for row in rows]
        finally:
            cur.close()

    def count_conversations(
        self,
        *,
        project_id: str | None = None,
        date_from: datetime | None = None,
        date_to: datetime | None = None,
        tool: str | None = None,
    ) -> int:
        conditions = ["message_count > 0"]
        params: list[object] = []

        if project_id:
            conditions.append("project_id = ?")
            params.append(project_id)
        if date_from:
            conditions.append("updated_at >= ?")
            params.append(date_from)
        if date_to:
            conditions.append("updated_at < ?")
            params.append(date_to)
        if tool:
            conditions.append("file_path LIKE ?")
            params.append(f"%{tool}%")

        where = " AND ".join(conditions)
        cur = self._read_cursor()
        try:
            row = cur.execute(
                f"SELECT COUNT(*)::BIGINT FROM conversations WHERE {where}",
                params,
            ).fetchone()
            return int(row[0]) if row else 0
        finally:
            cur.close()

    def validate_parquet_scan(self) -> None:
        """Health check — verifies DuckDB connection is alive."""
        cur = self._read_cursor()
        try:
            cur.execute("SELECT 1").fetchone()
        finally:
            cur.close()

    def get_conversation_meta(self, conversation_id: str) -> dict | None:
        cur = self._read_cursor()
        try:
            row = cur.execute(
                "SELECT conversation_id, project_id, title, created_at, "
                "updated_at, message_count, file_path "
                "FROM conversations WHERE conversation_id = ? LIMIT 1",
                [conversation_id],
            ).fetchone()
            if row is None:
                return None
            columns = [
                "conversation_id",
                "project_id",
                "title",
                "created_at",
                "updated_at",
                "message_count",
                "file_path",
            ]
            return dict(zip(columns, row))
        finally:
            cur.close()

    def get_conversation_record(self, conversation_id: str) -> dict | None:
        """Return full conversation including denormalized messages list."""
        meta = self.get_conversation_meta(conversation_id)
        if meta is None:
            return None

        cur = self._read_cursor()
        try:
            rows = cur.execute(
                "SELECT sequence, role, content, timestamp, has_code, code_blocks "
                "FROM messages WHERE conversation_id = ? ORDER BY sequence",
                [conversation_id],
            ).fetchall()
            messages = [
                {
                    "sequence": seq,
                    "role": role,
                    "content": content,
                    "timestamp": ts,
                    "has_code": hc,
                    "code_blocks": cb,
                }
                for seq, role, content, ts, hc, cb in rows
            ]
            meta["messages"] = messages
            return meta
        finally:
            cur.close()

    def get_statistics(self):
        cur = self._read_cursor()
        try:
            row = cur.execute(
                "SELECT COUNT(*)::BIGINT, "
                "  COALESCE(SUM(message_count), 0)::BIGINT, "
                "  COALESCE(AVG(message_count), 0)::DOUBLE, "
                "  COUNT(DISTINCT project_id)::BIGINT, "
                "  MIN(created_at), MAX(updated_at) "
                "FROM conversations"
            ).fetchone()
            if row is None:
                return IndexStatistics(0, 0, 0.0, 0, None, None)

            def _iso(v: object) -> str | None:
                if v is None:
                    return None
                return v.isoformat() if isinstance(v, datetime) else str(v)

            return IndexStatistics(
                total_conversations=int(row[0]),
                total_messages=int(row[1]),
                avg_messages=float(row[2]),
                total_projects=int(row[3]),
                earliest_date=_iso(row[4]),
                latest_date=_iso(row[5]),
            )
        finally:
            cur.close()

    # ------------------------------------------------------------------
    # Write operations
    # ------------------------------------------------------------------

    def upsert_conversation(
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
        files_mentioned: list[str] | None = None,
        git_branch: str | None = None,
    ) -> None:
        """Insert or replace a conversation row."""
        import json

        cur = self._write_cursor()
        cur.execute(
            "INSERT OR REPLACE INTO conversations "
            "(conversation_id, project_id, file_path, title, created_at, "
            "updated_at, message_count, full_text, file_hash, indexed_at, "
            "files_mentioned, git_branch) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            [
                conversation_id,
                project_id,
                file_path,
                title,
                created_at,
                updated_at,
                message_count,
                full_text,
                file_hash,
                indexed_at,
                json.dumps(files_mentioned) if files_mentioned else None,
                git_branch,
            ],
        )

    def insert_messages(
        self,
        conversation_id: str,
        messages: list[dict],
    ) -> None:
        """Bulk insert messages for a conversation.

        Deletes existing messages for the conversation_id first (upsert
        semantics at the conversation level).
        """
        import json

        cur = self._write_cursor()
        cur.execute(
            "DELETE FROM messages WHERE conversation_id = ?",
            [conversation_id],
        )
        for msg in messages:
            code_blocks = msg.get("code_blocks")
            cur.execute(
                "INSERT INTO messages "
                "(conversation_id, sequence, role, content, timestamp, "
                "has_code, code_blocks) VALUES (?, ?, ?, ?, ?, ?, ?)",
                [
                    conversation_id,
                    msg["sequence"],
                    msg["role"],
                    msg["content"],
                    msg.get("timestamp"),
                    msg.get("has_code", False),
                    json.dumps(code_blocks) if code_blocks else None,
                ],
            )

    def upsert_exchange(
        self,
        *,
        exchange_id: str,
        conversation_id: str,
        project_id: str | None,
        ply_start: int,
        ply_end: int,
        exchange_text: str,
        created_at: datetime,
    ) -> None:
        cur = self._write_cursor()
        cur.execute(
            "INSERT INTO exchanges "
            "(exchange_id, conversation_id, project_id, ply_start, "
            "ply_end, exchange_text, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?) "
            "ON CONFLICT (exchange_id) DO UPDATE SET "
            "exchange_text = EXCLUDED.exchange_text, "
            "created_at = EXCLUDED.created_at",
            [
                exchange_id,
                conversation_id,
                project_id,
                ply_start,
                ply_end,
                exchange_text,
                created_at,
            ],
        )

    def upsert_embedding(
        self,
        exchange_id: str,
        embedding: list[float],
    ) -> None:
        if len(embedding) != EMBEDDING_DIM:
            raise ValueError(
                f"Embedding dimension mismatch: got {len(embedding)}, "
                f"expected {EMBEDDING_DIM}"
            )
        cur = self._write_cursor()
        cur.execute(
            "INSERT OR REPLACE INTO verbatim_embeddings "
            "(exchange_id, embedding) VALUES (?, ?::FLOAT[384])",
            [exchange_id, embedding],
        )

    def upsert_file_state(
        self,
        *,
        file_path: str,
        conversation_id: str | None = None,
        project_id: str | None = None,
        connector_name: str | None = None,
        status: str = "indexed",
        file_size: int = 0,
        file_hash: str | None = None,
        updated_at: datetime | None = None,
    ) -> None:
        cur = self._write_cursor()
        cur.execute(
            "INSERT OR REPLACE INTO source_file_state "
            "(file_path, conversation_id, project_id, connector_name, "
            "status, file_size, file_hash, updated_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            [
                file_path,
                conversation_id,
                project_id,
                connector_name,
                status,
                file_size,
                file_hash,
                updated_at or datetime.now(),
            ],
        )

    def insert_code_block(
        self,
        *,
        conversation_id: str,
        project_id: str,
        message_index: int,
        block_index: int,
        code: str,
        code_hash: str,
        lines: int,
        connector: str | None = None,
        file_path: str | None = None,
        title: str | None = None,
        conversation_created_at: datetime | None = None,
        conversation_updated_at: datetime | None = None,
        role: str | None = None,
        message_timestamp: datetime | None = None,
        fence_language: str | None = None,
        language: str | None = None,
        language_source: str | None = None,
        functions: list[str] | None = None,
        classes: list[str] | None = None,
        imports: list[str] | None = None,
    ) -> None:
        import json

        cur = self._write_cursor()
        cur.execute(
            "INSERT OR REPLACE INTO code_blocks "
            "(conversation_id, project_id, connector, file_path, title, "
            "conversation_created_at, conversation_updated_at, "
            "message_index, block_index, role, message_timestamp, "
            "fence_language, language, language_source, "
            "functions, classes, imports, code, code_hash, lines) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            [
                conversation_id,
                project_id,
                connector,
                file_path,
                title,
                conversation_created_at,
                conversation_updated_at,
                message_index,
                block_index,
                role,
                message_timestamp,
                fence_language,
                language,
                language_source,
                json.dumps(functions) if functions else None,
                json.dumps(classes) if classes else None,
                json.dumps(imports) if imports else None,
                code,
                code_hash,
                lines,
            ],
        )

    # ------------------------------------------------------------------
    # Query helpers
    # ------------------------------------------------------------------

    def get_row_counts(self) -> dict[str, int]:
        return table_row_counts(self._conn)

    def get_exchange_count(self) -> int:
        cur = self._read_cursor()
        try:
            row = cur.execute("SELECT COUNT(*) FROM exchanges").fetchone()
            return int(row[0]) if row else 0
        finally:
            cur.close()

    def get_embedding_count(self) -> int:
        cur = self._read_cursor()
        try:
            row = cur.execute("SELECT COUNT(*) FROM verbatim_embeddings").fetchone()
            return int(row[0]) if row else 0
        finally:
            cur.close()
