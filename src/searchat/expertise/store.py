"""DuckDB-backed persistence for the L2 expertise knowledge store."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from searchat.expertise.models import (
    ExpertiseQuery,
    ExpertiseRecord,
    ExpertiseSeverity,
    ExpertiseType,
)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _row_to_record(row: tuple[Any, ...]) -> ExpertiseRecord:
    (
        id_,
        type_,
        domain,
        project,
        content,
        name,
        example,
        rationale,
        alternatives,
        resolution,
        severity,
        confidence,
        source_conversation_id,
        source_agent,
        tags,
        created_at,
        last_validated,
        validation_count,
        is_active,
    ) = row

    return ExpertiseRecord(
        id=id_,
        type=ExpertiseType(type_),
        domain=domain,
        project=project,
        content=content,
        name=name,
        example=example,
        rationale=rationale,
        alternatives_considered=json.loads(alternatives) if alternatives else None,
        resolution=resolution,
        severity=ExpertiseSeverity(severity) if severity else None,
        confidence=float(confidence),
        source_conversation_id=source_conversation_id,
        source_agent=source_agent,
        tags=json.loads(tags) if tags else [],
        created_at=created_at if isinstance(created_at, datetime) else datetime.fromisoformat(str(created_at)),
        last_validated=last_validated if isinstance(last_validated, datetime) else datetime.fromisoformat(str(last_validated)),
        validation_count=int(validation_count),
        is_active=bool(is_active),
    )


_SELECT_COLS = """
    id, type, domain, project, content, name, example, rationale,
    alternatives, resolution, severity, confidence,
    source_conversation_id, source_agent, tags,
    created_at, last_validated, validation_count, is_active
"""


class ExpertiseStore:
    """Persistent DuckDB store for expertise records."""

    def __init__(self, data_dir: Path) -> None:
        self._db_path = data_dir / "expertise" / "expertise.duckdb"
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._ensure_tables()

    def _connect(self):
        import duckdb
        return duckdb.connect(database=str(self._db_path))

    def _ensure_tables(self) -> None:
        con = self._connect()
        try:
            con.execute("""
                CREATE TABLE IF NOT EXISTS expertise_records (
                    id              TEXT PRIMARY KEY,
                    type            TEXT NOT NULL,
                    domain          TEXT NOT NULL,
                    project         TEXT,
                    content         TEXT NOT NULL,
                    name            TEXT,
                    example         TEXT,
                    rationale       TEXT,
                    alternatives    TEXT,
                    resolution      TEXT,
                    severity        TEXT,
                    confidence      DOUBLE DEFAULT 1.0,
                    source_conversation_id TEXT,
                    source_agent    TEXT,
                    tags            TEXT,
                    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    last_validated  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    validation_count INTEGER DEFAULT 1,
                    is_active       BOOLEAN DEFAULT TRUE
                )
            """)
            con.execute("""
                CREATE TABLE IF NOT EXISTS expertise_domains (
                    name            TEXT PRIMARY KEY,
                    description     TEXT,
                    record_count    INTEGER DEFAULT 0,
                    last_updated    TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            con.execute("CREATE INDEX IF NOT EXISTS idx_expertise_domain ON expertise_records(domain)")
            con.execute("CREATE INDEX IF NOT EXISTS idx_expertise_project ON expertise_records(project)")
            con.execute("CREATE INDEX IF NOT EXISTS idx_expertise_type ON expertise_records(type)")
            con.execute("CREATE INDEX IF NOT EXISTS idx_expertise_active ON expertise_records(is_active)")
        finally:
            con.close()

    def insert(self, record: ExpertiseRecord) -> str:
        con = self._connect()
        try:
            con.execute(
                f"""
                INSERT INTO expertise_records (
                    id, type, domain, project, content, name, example, rationale,
                    alternatives, resolution, severity, confidence,
                    source_conversation_id, source_agent, tags,
                    created_at, last_validated, validation_count, is_active
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    record.id,
                    record.type.value,
                    record.domain,
                    record.project,
                    record.content,
                    record.name,
                    record.example,
                    record.rationale,
                    json.dumps(record.alternatives_considered) if record.alternatives_considered is not None else None,
                    record.resolution,
                    record.severity.value if record.severity else None,
                    record.confidence,
                    record.source_conversation_id,
                    record.source_agent,
                    json.dumps(record.tags),
                    record.created_at,
                    record.last_validated,
                    record.validation_count,
                    record.is_active,
                ],
            )
            # Upsert domain, incrementing record_count
            con.execute(
                """
                INSERT INTO expertise_domains (name, description, record_count, last_updated)
                VALUES (?, '', 1, ?)
                ON CONFLICT (name) DO UPDATE SET
                    record_count = record_count + 1,
                    last_updated = excluded.last_updated
                """,
                [record.domain, _utcnow()],
            )
        finally:
            con.close()
        return record.id

    def get(self, record_id: str) -> ExpertiseRecord | None:
        con = self._connect()
        try:
            row = con.execute(
                f"SELECT {_SELECT_COLS} FROM expertise_records WHERE id = ?",
                [record_id],
            ).fetchone()
        finally:
            con.close()
        if row is None:
            return None
        return _row_to_record(row)

    def update(self, record_id: str, **fields: Any) -> bool:
        if not fields:
            return False

        allowed = {
            "type", "domain", "project", "content", "name", "example",
            "rationale", "alternatives", "resolution", "severity",
            "confidence", "source_conversation_id", "source_agent",
            "tags", "is_active",
        }
        invalid = set(fields) - allowed
        if invalid:
            raise ValueError(f"Cannot update fields: {invalid}")

        # Serialize JSON fields
        params: list[Any] = []
        set_clauses: list[str] = []
        for col, val in fields.items():
            set_clauses.append(f"{col} = ?")
            if col in ("tags", "alternatives") and isinstance(val, list):
                params.append(json.dumps(val))
            elif col == "type" and isinstance(val, ExpertiseType):
                params.append(val.value)
            elif col == "severity" and isinstance(val, ExpertiseSeverity):
                params.append(val.value)
            else:
                params.append(val)

        params.append(record_id)
        con = self._connect()
        try:
            result = con.execute(
                f"UPDATE expertise_records SET {', '.join(set_clauses)} WHERE id = ?",
                params,
            )
            count = result.rowcount
        finally:
            con.close()
        return count > 0

    def soft_delete(self, record_id: str) -> bool:
        con = self._connect()
        try:
            result = con.execute(
                "UPDATE expertise_records SET is_active = FALSE WHERE id = ?",
                [record_id],
            )
            count = result.rowcount
        finally:
            con.close()
        return count > 0

    def query(self, q: ExpertiseQuery) -> list[ExpertiseRecord]:
        conditions: list[str] = []
        params: list[Any] = []

        if q.active_only:
            conditions.append("is_active = TRUE")

        if q.domain is not None:
            conditions.append("domain = ?")
            params.append(q.domain)

        if q.type is not None:
            conditions.append("type = ?")
            params.append(q.type.value)

        if q.project is not None:
            conditions.append("project = ?")
            params.append(q.project)

        if q.severity is not None:
            conditions.append("severity = ?")
            params.append(q.severity.value)

        if q.min_confidence is not None:
            conditions.append("confidence >= ?")
            params.append(q.min_confidence)

        if q.after is not None:
            conditions.append("created_at >= ?")
            params.append(q.after)

        if q.agent is not None:
            conditions.append("source_agent = ?")
            params.append(q.agent)

        if q.q is not None:
            conditions.append("(content ILIKE ? OR name ILIKE ?)")
            pattern = f"%{q.q}%"
            params.extend([pattern, pattern])

        where = f"WHERE {' AND '.join(conditions)}" if conditions else ""

        sql = f"""
            SELECT {_SELECT_COLS}
            FROM expertise_records
            {where}
            ORDER BY created_at DESC
            LIMIT ? OFFSET ?
        """
        params.extend([q.limit, q.offset])

        con = self._connect()
        try:
            rows = con.execute(sql, params).fetchall()
        finally:
            con.close()

        records = [_row_to_record(r) for r in rows]

        # Post-filter by tags (DuckDB TEXT storage; check JSON membership)
        if q.tags:
            filtered: list[ExpertiseRecord] = []
            for rec in records:
                if any(t in rec.tags for t in q.tags):
                    filtered.append(rec)
            return filtered

        return records

    def validate_record(self, record_id: str) -> bool:
        con = self._connect()
        try:
            result = con.execute(
                """
                UPDATE expertise_records
                SET validation_count = validation_count + 1,
                    last_validated = ?
                WHERE id = ?
                """,
                [_utcnow(), record_id],
            )
            count = result.rowcount
        finally:
            con.close()
        return count > 0

    def list_domains(self) -> list[dict[str, Any]]:
        con = self._connect()
        try:
            rows = con.execute(
                "SELECT name, description, record_count, last_updated FROM expertise_domains ORDER BY name"
            ).fetchall()
        finally:
            con.close()
        return [
            {
                "name": r[0],
                "description": r[1],
                "record_count": int(r[2]),
                "last_updated": r[3].isoformat() if isinstance(r[3], datetime) else str(r[3]),
            }
            for r in rows
        ]

    def create_domain(self, name: str, description: str = "") -> None:
        con = self._connect()
        try:
            con.execute(
                """
                INSERT INTO expertise_domains (name, description, record_count, last_updated)
                VALUES (?, ?, 0, ?)
                ON CONFLICT (name) DO NOTHING
                """,
                [name, description, _utcnow()],
            )
        finally:
            con.close()

    def get_domain_stats(self, domain: str) -> dict[str, Any]:
        con = self._connect()
        try:
            domain_row = con.execute(
                "SELECT name, description, record_count, last_updated FROM expertise_domains WHERE name = ?",
                [domain],
            ).fetchone()

            stats_row = con.execute(
                """
                SELECT
                    COUNT(*)::BIGINT AS total,
                    SUM(CASE WHEN is_active THEN 1 ELSE 0 END)::BIGINT AS active,
                    AVG(confidence)::DOUBLE AS avg_confidence,
                    MAX(created_at) AS latest_created
                FROM expertise_records
                WHERE domain = ?
                """,
                [domain],
            ).fetchone()

            type_rows = con.execute(
                """
                SELECT type, COUNT(*)::BIGINT AS cnt
                FROM expertise_records
                WHERE domain = ? AND is_active = TRUE
                GROUP BY type
                ORDER BY cnt DESC
                """,
                [domain],
            ).fetchall()
        finally:
            con.close()

        result: dict[str, Any] = {"domain": domain}

        if domain_row:
            result["description"] = domain_row[1]
            result["record_count"] = int(domain_row[2])
            result["last_updated"] = (
                domain_row[3].isoformat() if isinstance(domain_row[3], datetime) else str(domain_row[3])
            )
        else:
            result["description"] = None
            result["record_count"] = 0
            result["last_updated"] = None

        if stats_row:
            result["total_records"] = int(stats_row[0]) if stats_row[0] else 0
            result["active_records"] = int(stats_row[1]) if stats_row[1] else 0
            result["avg_confidence"] = float(stats_row[2]) if stats_row[2] is not None else 0.0
            result["latest_created"] = (
                stats_row[3].isoformat() if isinstance(stats_row[3], datetime) else str(stats_row[3])
                if stats_row[3] else None
            )
        else:
            result["total_records"] = 0
            result["active_records"] = 0
            result["avg_confidence"] = 0.0
            result["latest_created"] = None

        result["by_type"] = {r[0]: int(r[1]) for r in type_rows}
        return result

    def close(self) -> None:
        # Connections are per-operation; nothing to close globally.
        pass
