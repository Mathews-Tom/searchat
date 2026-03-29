"""DuckDB persistent storage for memory palace distillation data."""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

import duckdb

from searchat.models.domain import DistilledObject, FileTouched, Room, RoomObject


class PalaceStorage:
    """Persistent DuckDB storage for distilled objects, rooms, and junctions."""

    def __init__(
        self, data_dir: Path, conn: duckdb.DuckDBPyConnection | None = None,
    ) -> None:
        self.data_dir = data_dir
        if conn is not None:
            self.conn = conn
            self._external_conn = True
        else:
            self.data_dir.mkdir(parents=True, exist_ok=True)
            self.db_path = data_dir / "palace.duckdb"
            self.conn = duckdb.connect(str(self.db_path))
            self._external_conn = False
        self._ensure_tables()
        self._change_token = 0

    def _ensure_tables(self) -> None:
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS objects (
                object_id VARCHAR PRIMARY KEY,
                project_id VARCHAR NOT NULL,
                conversation_id VARCHAR NOT NULL,
                conv_title VARCHAR,
                ply_start INTEGER NOT NULL,
                ply_end INTEGER NOT NULL,
                files_touched JSON,
                exchange_core VARCHAR NOT NULL,
                specific_context VARCHAR NOT NULL,
                created_at TIMESTAMP NOT NULL,
                exchange_at TIMESTAMP NOT NULL,
                embedding_id BIGINT,
                distilled_text VARCHAR NOT NULL,
                UNIQUE(conversation_id, ply_start, ply_end)
            )
        """)
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS rooms (
                room_id VARCHAR PRIMARY KEY,
                room_type VARCHAR NOT NULL,
                room_key VARCHAR NOT NULL,
                room_label VARCHAR NOT NULL,
                project_id VARCHAR,
                created_at TIMESTAMP NOT NULL,
                updated_at TIMESTAMP NOT NULL,
                object_count INTEGER DEFAULT 0
            )
        """)
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS room_objects (
                room_id VARCHAR NOT NULL,
                object_id VARCHAR NOT NULL,
                relevance FLOAT NOT NULL,
                placed_at TIMESTAMP NOT NULL,
                PRIMARY KEY (room_id, object_id),
                FOREIGN KEY (room_id) REFERENCES rooms(room_id),
                FOREIGN KEY (object_id) REFERENCES objects(object_id)
            )
        """)
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS skipped_conversations (
                conversation_id VARCHAR PRIMARY KEY,
                reason VARCHAR NOT NULL,
                skipped_at TIMESTAMP NOT NULL
            )
        """)

    # --- Reads ---

    def get_existing_object_keys(
        self, conversation_id: str | None = None,
    ) -> set[tuple[str, int, int]]:
        """Return set of (conversation_id, ply_start, ply_end) for dedup."""
        if conversation_id is not None:
            rows = self.conn.execute(
                "SELECT conversation_id, ply_start, ply_end FROM objects WHERE conversation_id = ?",
                [conversation_id],
            ).fetchall()
        else:
            rows = self.conn.execute(
                "SELECT conversation_id, ply_start, ply_end FROM objects",
            ).fetchall()
        return {(r[0], r[1], r[2]) for r in rows}

    def get_distilled_conversation_ids(self) -> set[str]:
        rows = self.conn.execute(
            "SELECT DISTINCT conversation_id FROM objects",
        ).fetchall()
        return {r[0] for r in rows}

    def get_skipped_conversation_ids(self) -> set[str]:
        rows = self.conn.execute(
            "SELECT conversation_id FROM skipped_conversations",
        ).fetchall()
        return {r[0] for r in rows}

    def mark_conversation_skipped(self, conversation_id: str, reason: str) -> None:
        self.conn.execute("""
            INSERT INTO skipped_conversations (conversation_id, reason, skipped_at)
            VALUES (?, ?, ?)
            ON CONFLICT (conversation_id) DO UPDATE SET
                reason = EXCLUDED.reason,
                skipped_at = EXCLUDED.skipped_at
        """, [conversation_id, reason, datetime.utcnow()])

    def clear_llm_error_skips(self) -> int:
        """Clear skipped conversations that failed due to LLM errors.

        Returns the number of conversations cleared.
        """
        result = self.conn.execute("""
            DELETE FROM skipped_conversations
            WHERE reason LIKE 'llm_error%'
            RETURNING conversation_id
        """).fetchall()
        return len(result)

    def get_change_token(self) -> int:
        return self._change_token

    def get_objects_in_room(self, room_id: str) -> list[DistilledObject]:
        rows = self.conn.execute("""
            SELECT o.object_id, o.project_id, o.conversation_id,
                   o.conv_title, o.ply_start, o.ply_end, o.files_touched,
                   o.exchange_core, o.specific_context,
                   o.created_at, o.exchange_at, o.embedding_id, o.distilled_text
            FROM room_objects ro
            JOIN objects o ON ro.object_id = o.object_id
            WHERE ro.room_id = ?
            ORDER BY o.exchange_at ASC
        """, [room_id]).fetchall()
        return [self._row_to_object(r) for r in rows]

    def find_rooms_by_keyword(self, query: str, limit: int = 20) -> list[Room]:
        rows = self.conn.execute("""
            SELECT room_id, room_type, room_key, room_label, project_id,
                   created_at, updated_at, object_count
            FROM rooms
            WHERE room_label ILIKE '%' || ? || '%'
               OR room_key ILIKE '%' || ? || '%'
            ORDER BY object_count DESC
            LIMIT ?
        """, [query, query, limit]).fetchall()
        return [self._row_to_room(r) for r in rows]

    def get_object_by_id(self, object_id: str) -> DistilledObject:
        rows = self.conn.execute("""
            SELECT object_id, project_id, conversation_id, conv_title,
                   ply_start, ply_end, files_touched,
                   exchange_core, specific_context,
                   created_at, exchange_at, embedding_id, distilled_text
            FROM objects WHERE object_id = ?
        """, [object_id]).fetchall()
        if not rows:
            raise KeyError(f"Object not found: {object_id}")
        return self._row_to_object(rows[0])

    def get_objects_by_ids(self, object_ids: list[str]) -> list[DistilledObject]:
        if not object_ids:
            return []
        placeholders = ", ".join(["?" for _ in object_ids])
        rows = self.conn.execute(f"""
            SELECT object_id, project_id, conversation_id, conv_title,
                   ply_start, ply_end, files_touched,
                   exchange_core, specific_context,
                   created_at, exchange_at, embedding_id, distilled_text
            FROM objects WHERE object_id IN ({placeholders})
        """, object_ids).fetchall()
        return [self._row_to_object(r) for r in rows]

    def get_rooms_by_ids(self, room_ids: list[str]) -> list[Room]:
        if not room_ids:
            return []
        placeholders = ", ".join(["?" for _ in room_ids])
        rows = self.conn.execute(f"""
            SELECT room_id, room_type, room_key, room_label, project_id,
                   created_at, updated_at, object_count
            FROM rooms WHERE room_id IN ({placeholders})
        """, room_ids).fetchall()
        return [self._row_to_room(r) for r in rows]

    def get_all_rooms(self, project_id: str | None = None) -> list[Room]:
        if project_id is not None:
            rows = self.conn.execute("""
                SELECT room_id, room_type, room_key, room_label, project_id,
                       created_at, updated_at, object_count
                FROM rooms WHERE project_id = ?
                ORDER BY updated_at DESC
            """, [project_id]).fetchall()
        else:
            rows = self.conn.execute("""
                SELECT room_id, room_type, room_key, room_label, project_id,
                       created_at, updated_at, object_count
                FROM rooms ORDER BY updated_at DESC
            """).fetchall()
        return [self._row_to_room(r) for r in rows]

    def get_all_objects(self, project_id: str | None = None) -> list[DistilledObject]:
        if project_id is not None:
            rows = self.conn.execute("""
                SELECT object_id, project_id, conversation_id, conv_title,
                       ply_start, ply_end, files_touched,
                       exchange_core, specific_context,
                       created_at, exchange_at, embedding_id, distilled_text
                FROM objects WHERE project_id = ?
                ORDER BY exchange_at DESC
            """, [project_id]).fetchall()
        else:
            rows = self.conn.execute("""
                SELECT object_id, project_id, conversation_id, conv_title,
                       ply_start, ply_end, files_touched,
                       exchange_core, specific_context,
                       created_at, exchange_at, embedding_id, distilled_text
                FROM objects ORDER BY exchange_at DESC
            """).fetchall()
        return [self._row_to_object(r) for r in rows]

    def get_room_object_pairs(
        self, object_ids: list[str] | None = None,
    ) -> list[tuple[str, str]]:
        if object_ids:
            placeholders = ", ".join(["?" for _ in object_ids])
            return self.conn.execute(
                f"SELECT object_id, room_id FROM room_objects WHERE object_id IN ({placeholders})",
                object_ids,
            ).fetchall()
        return self.conn.execute(
            "SELECT object_id, room_id FROM room_objects",
        ).fetchall()

    def get_rooms_for_object(self, object_id: str) -> list[Room]:
        rows = self.conn.execute("""
            SELECT r.room_id, r.room_type, r.room_key, r.room_label, r.project_id,
                   r.created_at, r.updated_at, r.object_count
            FROM room_objects ro
            JOIN rooms r ON ro.room_id = r.room_id
            WHERE ro.object_id = ?
        """, [object_id]).fetchall()
        return [self._row_to_room(r) for r in rows]

    def get_stats(self) -> dict[str, int]:
        """Return summary statistics for the palace."""
        obj_count = self.conn.execute("SELECT COUNT(*) FROM objects").fetchone()[0]
        room_count = self.conn.execute("SELECT COUNT(*) FROM rooms").fetchone()[0]
        conv_count = self.conn.execute(
            "SELECT COUNT(DISTINCT conversation_id) FROM objects",
        ).fetchone()[0]
        return {
            "total_objects": obj_count,
            "total_rooms": room_count,
            "total_conversations": conv_count,
        }

    # --- Writes ---

    def store_distillation_results(
        self,
        objects: list[DistilledObject],
        rooms: list[Room],
        junctions: list[RoomObject],
    ) -> None:
        try:
            self.conn.execute("ROLLBACK")
        except Exception:
            pass
        try:
            self.conn.execute("BEGIN TRANSACTION")
        except Exception:
            try:
                self.conn.execute("ROLLBACK")
            except Exception:
                pass
            self.conn.execute("BEGIN TRANSACTION")
        try:
            for obj in objects:
                ft_json = json.dumps(
                    [{"path": f.path, "action": f.action} for f in obj.files_touched],
                )
                self.conn.execute("""
                    INSERT INTO objects (
                        object_id, project_id, conversation_id, conv_title,
                        ply_start, ply_end, files_touched,
                        exchange_core, specific_context,
                        created_at, exchange_at, embedding_id, distilled_text
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT (object_id) DO NOTHING
                """, [
                    obj.object_id, obj.project_id, obj.conversation_id,
                    obj.conv_title,
                    obj.ply_start, obj.ply_end, ft_json,
                    obj.exchange_core, obj.specific_context,
                    obj.created_at, obj.exchange_at, obj.embedding_id,
                    obj.distilled_text,
                ])

            for room in rooms:
                self.conn.execute("""
                    INSERT INTO rooms (
                        room_id, room_type, room_key, room_label, project_id,
                        created_at, updated_at, object_count
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT (room_id) DO UPDATE SET
                        updated_at = EXCLUDED.updated_at,
                        object_count = EXCLUDED.object_count
                """, [
                    room.room_id, room.room_type, room.room_key,
                    room.room_label, room.project_id,
                    room.created_at, room.updated_at, room.object_count,
                ])

            if junctions:
                self.conn.executemany("""
                    INSERT INTO room_objects (room_id, object_id, relevance, placed_at)
                    VALUES (?, ?, ?, ?)
                    ON CONFLICT (room_id, object_id) DO NOTHING
                """, [
                    [j.room_id, j.object_id, j.relevance, j.placed_at]
                    for j in junctions
                ])

            self.conn.execute("COMMIT")
            self._change_token += 1
        except Exception:
            self.conn.execute("ROLLBACK")
            raise

    # --- Helpers ---

    def _row_to_object(self, row: tuple) -> DistilledObject:
        ft_raw = row[6]
        if isinstance(ft_raw, str):
            ft_data = json.loads(ft_raw)
        elif ft_raw is None:
            ft_data = []
        else:
            ft_data = ft_raw
        files = [FileTouched(path=f["path"], action=f["action"]) for f in ft_data]

        return DistilledObject(
            object_id=row[0],
            project_id=row[1],
            conversation_id=row[2],
            ply_start=row[4],
            ply_end=row[5],
            files_touched=files,
            exchange_core=row[7],
            specific_context=row[8],
            created_at=row[9],
            exchange_at=row[10],
            embedding_id=row[11],
            distilled_text=row[12],
            conv_title=row[3],
        )

    def _row_to_room(self, row: tuple) -> Room:
        return Room(
            room_id=row[0],
            room_type=row[1],
            room_key=row[2],
            room_label=row[3],
            project_id=row[4],
            created_at=row[5],
            updated_at=row[6],
            object_count=row[7],
        )

    def close(self) -> None:
        if not self._external_conn:
            self.conn.close()
