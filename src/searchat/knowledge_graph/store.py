"""DuckDB-backed edge store for the knowledge graph."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from searchat.knowledge_graph.models import EdgeType, KnowledgeEdge


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _row_to_edge(row: tuple[Any, ...]) -> KnowledgeEdge:
    id_, source_id, target_id, edge_type, metadata_json, created_at, created_by, resolution_id = row
    return KnowledgeEdge(
        id=id_,
        source_id=source_id,
        target_id=target_id,
        edge_type=EdgeType(edge_type),
        metadata=json.loads(metadata_json) if metadata_json else None,
        created_at=created_at if isinstance(created_at, datetime) else datetime.fromisoformat(str(created_at)),
        created_by=created_by,
        resolution_id=resolution_id,
    )


_SELECT_COLS = "id, source_id, target_id, edge_type, metadata, created_at, created_by, resolution_id"


class KnowledgeGraphStore:
    """Persistent DuckDB store for knowledge graph edges."""

    def __init__(self, data_dir: Path) -> None:
        self._db_path = data_dir / "knowledge_graph" / "knowledge_graph.duckdb"
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._ensure_tables()

    def _connect(self):
        import duckdb
        return duckdb.connect(database=str(self._db_path))

    def _ensure_tables(self) -> None:
        con = self._connect()
        try:
            con.execute("""
                CREATE TABLE IF NOT EXISTS knowledge_edges (
                    id              TEXT PRIMARY KEY,
                    source_id       TEXT NOT NULL,
                    target_id       TEXT NOT NULL,
                    edge_type       TEXT NOT NULL,
                    metadata        TEXT,
                    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    created_by      TEXT,
                    resolution_id   TEXT
                )
            """)
            con.execute(
                "CREATE INDEX IF NOT EXISTS idx_kg_source ON knowledge_edges(source_id)"
            )
            con.execute(
                "CREATE INDEX IF NOT EXISTS idx_kg_target ON knowledge_edges(target_id)"
            )
            con.execute(
                "CREATE INDEX IF NOT EXISTS idx_kg_edge_type ON knowledge_edges(edge_type)"
            )
        finally:
            con.close()

    # ------------------------------------------------------------------
    # CRUD
    # ------------------------------------------------------------------

    def create_edge(self, edge: KnowledgeEdge) -> str:
        con = self._connect()
        try:
            con.execute(
                """
                INSERT INTO knowledge_edges
                    (id, source_id, target_id, edge_type, metadata, created_at, created_by, resolution_id)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    edge.id,
                    edge.source_id,
                    edge.target_id,
                    edge.edge_type.value,
                    json.dumps(edge.metadata) if edge.metadata is not None else None,
                    edge.created_at,
                    edge.created_by,
                    edge.resolution_id,
                ],
            )
        finally:
            con.close()
        return edge.id

    def get_edge(self, edge_id: str) -> KnowledgeEdge | None:
        con = self._connect()
        try:
            row = con.execute(
                f"SELECT {_SELECT_COLS} FROM knowledge_edges WHERE id = ?",
                [edge_id],
            ).fetchone()
        finally:
            con.close()
        if row is None:
            return None
        return _row_to_edge(row)

    def update_edge(self, edge_id: str, **fields: Any) -> bool:
        allowed = {"edge_type", "metadata", "resolution_id", "created_by"}
        invalid = set(fields) - allowed
        if invalid:
            raise ValueError(f"Cannot update fields: {invalid}")
        if not fields:
            return False

        set_clauses: list[str] = []
        params: list[Any] = []
        for col, val in fields.items():
            set_clauses.append(f"{col} = ?")
            if col == "edge_type" and isinstance(val, EdgeType):
                params.append(val.value)
            elif col == "metadata" and isinstance(val, dict):
                params.append(json.dumps(val))
            else:
                params.append(val)

        params.append(edge_id)
        con = self._connect()
        try:
            before = con.execute(
                "SELECT COUNT(*) FROM knowledge_edges WHERE id = ?", [edge_id]
            ).fetchone()[0]
            if before == 0:
                return False
            con.execute(
                f"UPDATE knowledge_edges SET {', '.join(set_clauses)} WHERE id = ?",
                params,
            )
        finally:
            con.close()
        return True

    def delete_edge(self, edge_id: str) -> bool:
        con = self._connect()
        try:
            before = con.execute(
                "SELECT COUNT(*) FROM knowledge_edges WHERE id = ?", [edge_id]
            ).fetchone()[0]
            if before == 0:
                return False
            con.execute("DELETE FROM knowledge_edges WHERE id = ?", [edge_id])
        finally:
            con.close()
        return True

    # ------------------------------------------------------------------
    # Queries
    # ------------------------------------------------------------------

    def get_edges_for_record(
        self,
        record_id: str,
        edge_type: EdgeType | None = None,
        as_source: bool = True,
        as_target: bool = True,
    ) -> list[KnowledgeEdge]:
        conditions: list[str] = []
        params: list[Any] = []

        direction_parts: list[str] = []
        if as_source:
            direction_parts.append("source_id = ?")
            params.append(record_id)
        if as_target:
            direction_parts.append("target_id = ?")
            params.append(record_id)

        if not direction_parts:
            return []

        conditions.append(f"({' OR '.join(direction_parts)})")

        if edge_type is not None:
            conditions.append("edge_type = ?")
            params.append(edge_type.value)

        where = f"WHERE {' AND '.join(conditions)}"
        con = self._connect()
        try:
            rows = con.execute(
                f"SELECT {_SELECT_COLS} FROM knowledge_edges {where} ORDER BY created_at DESC",
                params,
            ).fetchall()
        finally:
            con.close()
        return [_row_to_edge(r) for r in rows]

    def get_contradictions(self, unresolved_only: bool = True) -> list[KnowledgeEdge]:
        if unresolved_only:
            sql = (
                f"SELECT {_SELECT_COLS} FROM knowledge_edges "
                "WHERE edge_type = ? AND resolution_id IS NULL "
                "ORDER BY created_at DESC"
            )
            params: list[Any] = [EdgeType.CONTRADICTS.value]
        else:
            sql = (
                f"SELECT {_SELECT_COLS} FROM knowledge_edges "
                "WHERE edge_type = ? "
                "ORDER BY created_at DESC"
            )
            params = [EdgeType.CONTRADICTS.value]

        con = self._connect()
        try:
            rows = con.execute(sql, params).fetchall()
        finally:
            con.close()
        return [_row_to_edge(r) for r in rows]

    def get_related(
        self,
        record_id: str,
        edge_types: list[EdgeType] | None = None,
        limit: int = 20,
    ) -> list[KnowledgeEdge]:
        params: list[Any] = [record_id, record_id]
        type_filter = ""
        if edge_types:
            placeholders = ", ".join("?" * len(edge_types))
            type_filter = f"AND edge_type IN ({placeholders})"
            params.extend(et.value for et in edge_types)

        params.append(limit)
        con = self._connect()
        try:
            rows = con.execute(
                f"""
                SELECT {_SELECT_COLS} FROM knowledge_edges
                WHERE (source_id = ? OR target_id = ?) {type_filter}
                ORDER BY created_at DESC
                LIMIT ?
                """,
                params,
            ).fetchall()
        finally:
            con.close()
        return [_row_to_edge(r) for r in rows]

    # ------------------------------------------------------------------
    # Bulk operations
    # ------------------------------------------------------------------

    def bulk_create_edges(self, edges: list[KnowledgeEdge]) -> list[str]:
        if not edges:
            return []
        con = self._connect()
        try:
            for edge in edges:
                con.execute(
                    """
                    INSERT INTO knowledge_edges
                        (id, source_id, target_id, edge_type, metadata, created_at, created_by, resolution_id)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    [
                        edge.id,
                        edge.source_id,
                        edge.target_id,
                        edge.edge_type.value,
                        json.dumps(edge.metadata) if edge.metadata is not None else None,
                        edge.created_at,
                        edge.created_by,
                        edge.resolution_id,
                    ],
                )
        finally:
            con.close()
        return [e.id for e in edges]

    def bulk_delete_edges(self, edge_ids: list[str]) -> int:
        if not edge_ids:
            return 0
        placeholders = ", ".join("?" * len(edge_ids))
        con = self._connect()
        try:
            before_row = con.execute(
                f"SELECT COUNT(*) FROM knowledge_edges WHERE id IN ({placeholders})",
                edge_ids,
            ).fetchone()
            count = int(before_row[0]) if before_row else 0
            if count > 0:
                con.execute(
                    f"DELETE FROM knowledge_edges WHERE id IN ({placeholders})",
                    edge_ids,
                )
        finally:
            con.close()
        return count

    def close(self) -> None:
        # Connections are per-operation; nothing to close globally.
        pass
