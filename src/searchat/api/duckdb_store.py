"""DuckDB-on-demand queries over the parquet index.

This module is used by API endpoints that should be fast even when the search
engine/model are still warming.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path


ConversationSort = str


@dataclass(frozen=True)
class IndexStatistics:
    total_conversations: int
    total_messages: int
    avg_messages: float
    total_projects: int
    earliest_date: str | None
    latest_date: str | None


class DuckDBStore:
    def __init__(self, search_dir: Path, *, memory_limit_mb: int | None = None) -> None:
        self._search_dir = search_dir
        self._conversations_dir = search_dir / "data" / "conversations"
        self._memory_limit_mb = memory_limit_mb

    def _conversation_parquets(self) -> list[Path]:
        if not self._conversations_dir.exists():
            return []
        return sorted(self._conversations_dir.glob("*.parquet"))

    def _connect(self):
        import duckdb

        con = duckdb.connect(database=":memory:")
        if self._memory_limit_mb is not None:
            con.execute(f"PRAGMA memory_limit='{int(self._memory_limit_mb)}MB'")
        return con

    def list_projects(self) -> list[str]:
        parquets = self._conversation_parquets()
        if not parquets:
            return []

        con = self._connect()
        try:
            # Project only the required column.
            query = """
            SELECT DISTINCT project_id
            FROM parquet_scan(?)
            WHERE message_count > 0
            ORDER BY project_id
            """
            rows = con.execute(query, [str(self._conversations_dir / "*.parquet")]).fetchall()
            return [r[0] for r in rows]
        finally:
            con.close()

    def list_project_summaries(self) -> list[dict]:
        parquets = self._conversation_parquets()
        if not parquets:
            return []

        con = self._connect()
        try:
            query = """
            SELECT
              project_id,
              COUNT(*)::BIGINT AS conversation_count,
              COALESCE(SUM(message_count), 0)::BIGINT AS message_count,
              MAX(updated_at) AS updated_at
            FROM parquet_scan(?)
            WHERE message_count > 0
            GROUP BY project_id
            ORDER BY project_id
            """
            rows = con.execute(query, [str(self._conversations_dir / "*.parquet")]).fetchall()
            summaries = []
            for project_id, conv_count, msg_count, updated_at in rows:
                updated_at_str = updated_at.isoformat() if isinstance(updated_at, datetime) else str(updated_at)
                summaries.append(
                    {
                        "project_id": project_id,
                        "conversation_count": int(conv_count),
                        "message_count": int(msg_count),
                        "updated_at": updated_at_str,
                    }
                )
            return summaries
        finally:
            con.close()

    def list_conversations(
        self,
        *,
        sort_by: ConversationSort = "length",
        project_id: str | None = None,
        date_from: datetime | None = None,
        date_to: datetime | None = None,
        tool: str | None = None,
        limit: int | None = None,
        offset: int = 0,
    ) -> list[dict]:
        parquets = self._conversation_parquets()
        if not parquets:
            return []

        order_by = {
            "length": "message_count DESC",
            "date_newest": "updated_at DESC",
            "date_oldest": "updated_at ASC",
            "title": "title ASC",
        }.get(sort_by, "message_count DESC")

        conditions = ["message_count > 0"]
        params: list[object] = [str(self._conversations_dir / "*.parquet")]

        if project_id:
            conditions.append("project_id = ?")
            params.append(project_id)

        if tool:
            tool_value = tool.lower()
            if tool_value == "opencode":
                conditions.append("project_id LIKE 'opencode-%'")
            elif tool_value == "vibe":
                conditions.append("project_id LIKE 'vibe-%'")
            elif tool_value == "claude":
                conditions.append("project_id NOT LIKE 'opencode-%'")
                conditions.append("project_id NOT LIKE 'vibe-%'")

        if date_from:
            conditions.append("updated_at >= ?")
            params.append(date_from)

        if date_to:
            conditions.append("updated_at < ?")
            params.append(date_to)

        where_clause = " AND ".join(conditions)

        con = self._connect()
        try:
            query = f"""
            SELECT
              conversation_id,
              project_id,
              title,
              created_at,
              updated_at,
              message_count,
              file_path,
              full_text
            FROM parquet_scan(?)
            WHERE {where_clause}
            ORDER BY {order_by}
            """

            if limit is not None:
                query += "\nLIMIT ?\nOFFSET ?"
                params.append(int(limit))
                params.append(int(offset))
            rows = con.execute(query, params).fetchall()
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
            con.close()

    def count_conversations(
        self,
        *,
        project_id: str | None = None,
        date_from: datetime | None = None,
        date_to: datetime | None = None,
        tool: str | None = None,
    ) -> int:
        parquets = self._conversation_parquets()
        if not parquets:
            return 0

        conditions = ["message_count > 0"]
        params: list[object] = [str(self._conversations_dir / "*.parquet")]

        if project_id:
            conditions.append("project_id = ?")
            params.append(project_id)

        if tool:
            tool_value = tool.lower()
            if tool_value == "opencode":
                conditions.append("project_id LIKE 'opencode-%'")
            elif tool_value == "vibe":
                conditions.append("project_id LIKE 'vibe-%'")
            elif tool_value == "claude":
                conditions.append("project_id NOT LIKE 'opencode-%'")
                conditions.append("project_id NOT LIKE 'vibe-%'")

        if date_from:
            conditions.append("updated_at >= ?")
            params.append(date_from)

        if date_to:
            conditions.append("updated_at < ?")
            params.append(date_to)

        where_clause = " AND ".join(conditions)

        con = self._connect()
        try:
            query = f"""
            SELECT COUNT(*)::BIGINT
            FROM parquet_scan(?)
            WHERE {where_clause}
            """
            row = con.execute(query, params).fetchone()
            if row is None:
                return 0
            return int(row[0])
        finally:
            con.close()

    def validate_parquet_scan(self) -> None:
        """Validate DuckDB can connect and scan parquet files.

        If no conversation parquets exist yet, this validates the DuckDB runtime
        only (connection + simple query).
        """
        con = self._connect()
        try:
            con.execute("SELECT 1").fetchone()

            parquets = self._conversation_parquets()
            if parquets:
                con.execute(
                    "SELECT 1 FROM parquet_scan(?) LIMIT 1",
                    [str(self._conversations_dir / "*.parquet")],
                ).fetchone()
        finally:
            con.close()

    def get_conversation_meta(self, conversation_id: str) -> dict | None:
        parquets = self._conversation_parquets()
        if not parquets:
            return None

        con = self._connect()
        try:
            query = """
            SELECT
              conversation_id,
              project_id,
              title,
              created_at,
              updated_at,
              message_count,
              file_path
            FROM parquet_scan(?)
            WHERE conversation_id = ?
            LIMIT 1
            """
            row = con.execute(query, [str(self._conversations_dir / "*.parquet"), conversation_id]).fetchone()
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
            con.close()

    def get_statistics(self) -> IndexStatistics:
        parquets = self._conversation_parquets()
        if not parquets:
            return IndexStatistics(
                total_conversations=0,
                total_messages=0,
                avg_messages=0.0,
                total_projects=0,
                earliest_date=None,
                latest_date=None,
            )

        con = self._connect()
        try:
            query = """
            SELECT
              COUNT(*)::BIGINT AS total_conversations,
              COALESCE(SUM(message_count), 0)::BIGINT AS total_messages,
              COALESCE(AVG(message_count), 0)::DOUBLE AS avg_messages,
              COUNT(DISTINCT project_id)::BIGINT AS total_projects,
              MIN(created_at) AS earliest_date,
              MAX(updated_at) AS latest_date
            FROM parquet_scan(?)
            """
            row = con.execute(query, [str(self._conversations_dir / "*.parquet")]).fetchone()
            if row is None:
                return IndexStatistics(
                    total_conversations=0,
                    total_messages=0,
                    avg_messages=0.0,
                    total_projects=0,
                    earliest_date=None,
                    latest_date=None,
                )

            earliest = row[4]
            latest = row[5]

            def _to_iso(value):
                if value is None:
                    return None
                if isinstance(value, datetime):
                    return value.isoformat()
                return str(value)

            return IndexStatistics(
                total_conversations=int(row[0]),
                total_messages=int(row[1]),
                avg_messages=float(row[2]),
                total_projects=int(row[3]),
                earliest_date=_to_iso(earliest),
                latest_date=_to_iso(latest),
            )
        finally:
            con.close()
