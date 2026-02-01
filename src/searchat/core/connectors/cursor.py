from __future__ import annotations

import hashlib
import json
import re
import sqlite3
from datetime import datetime
from pathlib import Path

from searchat.config import Config, PathResolver
from searchat.models import ConversationRecord, MessageRecord


class CursorConnector:
    name: str = "cursor"
    supported_extensions: tuple[str, ...] = (".json",)

    _VSCDB_SENTINEL = ".vscdb.cursor/"

    def discover_files(self, config: Config) -> list[Path]:
        pseudo_files: list[Path] = []

        for cursor_user_dir in PathResolver.resolve_cursor_dirs(config):
            global_storage = cursor_user_dir / "globalStorage"
            workspace_storage = cursor_user_dir / "workspaceStorage"

            db_files: list[Path] = []
            for candidate in (global_storage / "state.vscdb", global_storage / "global-state.vscdb"):
                if candidate.exists() and candidate.is_file():
                    db_files.append(candidate)

            if workspace_storage.exists() and workspace_storage.is_dir():
                for workspace_dir in workspace_storage.iterdir():
                    if not workspace_dir.is_dir():
                        continue
                    candidate = workspace_dir / "state.vscdb"
                    if candidate.exists() and candidate.is_file():
                        db_files.append(candidate)

            for db_path in db_files:
                try:
                    composer_ids = self._list_composer_ids(db_path)
                except Exception:
                    continue

                for composer_id in composer_ids:
                    pseudo_files.append(self._pseudo_path(db_path, composer_id))

        return pseudo_files

    def watch_dirs(self, config: Config) -> list[Path]:
        dirs: list[Path] = []
        for cursor_user_dir in PathResolver.resolve_cursor_dirs(config):
            for candidate in (cursor_user_dir / "globalStorage", cursor_user_dir / "workspaceStorage"):
                if candidate.exists() and candidate.is_dir():
                    dirs.append(candidate)
        return dirs

    def can_parse(self, path: Path) -> bool:
        normalized = str(path).lower().replace("\\", "/")
        return normalized.endswith(".json") and (self._VSCDB_SENTINEL in normalized)

    def parse(self, path: Path, embedding_id: int) -> ConversationRecord:
        db_path, composer_id = self._decode_pseudo_path(path)

        con = self._connect_ro(db_path)
        try:
            table, key_col, value_col = self._find_kv_table(con)
            composer = self._load_composer(con, table, key_col, value_col, composer_id)

            headers = composer.get("fullConversationHeadersOnly")
            if not isinstance(headers, list) or not headers:
                raise ValueError(f"Cursor composer has no conversation headers: {composer_id}")

            bubble_ids: list[tuple[str, int]] = []
            for entry in headers:
                if not isinstance(entry, dict):
                    continue
                bubble_id = entry.get("bubbleId")
                bubble_type = entry.get("type")
                if isinstance(bubble_id, str) and isinstance(bubble_type, int):
                    bubble_ids.append((bubble_id, bubble_type))

            if not bubble_ids:
                raise ValueError(f"Cursor composer has no bubble ids: {composer_id}")

            bubbles = self._load_bubbles(con, table, value_col)

        finally:
            con.close()

        messages: list[MessageRecord] = []
        full_text_parts: list[str] = []

        for bubble_id, bubble_type in bubble_ids:
            bubble = bubbles.get(bubble_id)
            if bubble is None:
                raise ValueError(f"Missing Cursor bubble record: {bubble_id}")

            role = "user" if bubble_type == 1 else "assistant" if bubble_type == 2 else "assistant"
            content = self._extract_bubble_text(bubble)
            if not content:
                continue

            timestamp = self._bubble_timestamp(bubble)
            if timestamp is None:
                timestamp = datetime.fromtimestamp(db_path.stat().st_mtime)

            code_blocks = re.findall(r"```(?:\w+)?\n(.*?)```", content, re.DOTALL)
            has_code = len(code_blocks) > 0

            messages.append(
                MessageRecord(
                    sequence=len(messages),
                    role=role,
                    content=content,
                    timestamp=timestamp,
                    has_code=has_code,
                    code_blocks=code_blocks,
                )
            )
            full_text_parts.append(content)

        title = self._title_from_messages(messages) or "Untitled Cursor Chat"

        created_at = self._timestamp_ms_to_datetime(composer.get("createdAt"))
        updated_at = self._timestamp_ms_to_datetime(composer.get("lastUpdatedAt"))
        if created_at is None:
            created_at = messages[0].timestamp if messages else datetime.fromtimestamp(db_path.stat().st_mtime)
        if updated_at is None:
            updated_at = messages[-1].timestamp if messages else datetime.fromtimestamp(db_path.stat().st_mtime)

        project_id = self._project_id_from_db_path(db_path)

        file_path = str(path)
        file_hash = hashlib.sha256(
            json.dumps(
                {
                    "composer": composer,
                    "bubbles": [bubbles.get(bid) for bid, _t in bubble_ids],
                },
                ensure_ascii=True,
                sort_keys=True,
                default=str,
            ).encode("utf-8")
        ).hexdigest()

        full_text = "\n\n".join(full_text_parts)

        return ConversationRecord(
            conversation_id=composer_id,
            project_id=project_id,
            file_path=file_path,
            title=title,
            created_at=created_at,
            updated_at=updated_at,
            message_count=len(messages),
            messages=messages,
            full_text=full_text,
            embedding_id=embedding_id,
            file_hash=file_hash,
            indexed_at=datetime.now(),
        )

    def _connect_ro(self, db_path: Path) -> sqlite3.Connection:
        if not db_path.exists():
            raise FileNotFoundError(f"Cursor DB does not exist: {db_path}")
        uri = f"file:{db_path.as_posix()}?mode=ro"
        return sqlite3.connect(uri, uri=True)

    def _find_kv_table(self, con: sqlite3.Connection) -> tuple[str, str, str]:
        rows = con.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
        tables = [r[0] for r in rows if isinstance(r[0], str)]

        def columns(table: str) -> list[str]:
            cols = con.execute(f"PRAGMA table_info({table})").fetchall()
            out: list[str] = []
            for c in cols:
                name = c[1]
                if isinstance(name, str):
                    out.append(name)
            return out

        for preferred in ("ItemTable", "cursorDiskKV"):
            if preferred in tables:
                cols = columns(preferred)
                if "key" in cols and "value" in cols:
                    return preferred, "key", "value"

        for table in tables:
            cols = columns(table)
            if "key" in cols and "value" in cols:
                return table, "key", "value"

        raise RuntimeError("Could not find Cursor key/value table with columns 'key' and 'value'")

    def _list_composer_ids(self, db_path: Path) -> list[str]:
        con = self._connect_ro(db_path)
        try:
            table, key_col, value_col = self._find_kv_table(con)
            rows = con.execute(
                f"SELECT {key_col}, {value_col} FROM {table} WHERE {key_col} LIKE ?",
                ("%composerData:%",),
            ).fetchall()
        finally:
            con.close()

        ids: set[str] = set()
        for key, value in rows:
            if not isinstance(value, str):
                continue
            try:
                data = json.loads(value)
            except json.JSONDecodeError:
                continue
            if not isinstance(data, dict):
                continue
            composer_id = data.get("composerId")
            if isinstance(composer_id, str) and composer_id.strip():
                ids.add(composer_id.strip())
                continue
            if isinstance(key, str) and "composerData:" in key:
                tail = key.split("composerData:", 1)[1]
                if tail:
                    ids.add(tail)

        return sorted(ids)

    def _load_composer(
        self,
        con: sqlite3.Connection,
        table: str,
        key_col: str,
        value_col: str,
        composer_id: str,
    ) -> dict:
        rows = con.execute(
            f"SELECT {value_col} FROM {table} WHERE {key_col} LIKE ? LIMIT 1",
            (f"%composerData:{composer_id}%",),
        ).fetchall()
        if not rows:
            raise ValueError(f"Composer record not found: {composer_id}")
        value = rows[0][0]
        if not isinstance(value, str):
            raise ValueError(f"Composer record is not JSON text: {composer_id}")
        data = json.loads(value)
        if not isinstance(data, dict):
            raise ValueError(f"Composer record is not an object: {composer_id}")
        return data

    def _load_bubbles(self, con: sqlite3.Connection, table: str, value_col: str) -> dict[str, dict]:
        bubbles: dict[str, dict] = {}
        rows = con.execute(
            f"SELECT {value_col} FROM {table} WHERE {value_col} LIKE ?",
            ("%\"bubbleId\"%",),
        ).fetchall()
        for (value,) in rows:
            if not isinstance(value, str):
                continue
            try:
                data = json.loads(value)
            except json.JSONDecodeError:
                continue
            if not isinstance(data, dict):
                continue
            bubble_id = data.get("bubbleId")
            if isinstance(bubble_id, str) and bubble_id.strip():
                bubbles[bubble_id.strip()] = data
        return bubbles

    def _extract_bubble_text(self, bubble: dict) -> str:
        text = bubble.get("rawText")
        if isinstance(text, str) and text.strip():
            return text.strip()
        text = bubble.get("text")
        if isinstance(text, str) and text.strip():
            return text.strip()
        return ""

    def _bubble_timestamp(self, bubble: dict) -> datetime | None:
        timing = bubble.get("timingInfo")
        if isinstance(timing, dict):
            for key in ("clientEndTime", "clientSettleTime", "clientRpcSendTime"):
                ts = self._timestamp_ms_to_datetime(timing.get(key))
                if ts is not None:
                    return ts
        return self._timestamp_ms_to_datetime(bubble.get("timestamp"))

    def _timestamp_ms_to_datetime(self, value: object) -> datetime | None:
        if isinstance(value, (int, float)):
            try:
                return datetime.fromtimestamp(value / 1000)
            except (OSError, ValueError):
                return None
        return None

    def _title_from_messages(self, messages: list[MessageRecord]) -> str | None:
        for msg in messages:
            if msg.role == "user" and msg.content.strip():
                return msg.content.strip().splitlines()[0][:100]
        for msg in messages:
            if msg.content.strip():
                return msg.content.strip().splitlines()[0][:100]
        return None

    def _pseudo_path(self, db_path: Path, composer_id: str) -> Path:
        return Path(f"{db_path.as_posix()}.cursor/{composer_id}.json")

    def _decode_pseudo_path(self, path: Path) -> tuple[Path, str]:
        normalized = str(path).replace("\\", "/")
        lowered = normalized.lower()
        marker = self._VSCDB_SENTINEL
        pos = lowered.find(marker)
        if pos == -1:
            raise ValueError(f"Not a Cursor pseudo path: {path}")

        db_prefix = normalized[:pos]
        db_path = Path(db_prefix + ".vscdb")
        composer_id = path.stem
        if not composer_id:
            raise ValueError(f"Invalid Cursor pseudo path (missing composer id): {path}")
        return db_path, composer_id

    def _project_id_from_db_path(self, db_path: Path) -> str:
        parts = [p.lower() for p in db_path.parts]
        if "workspacestorage" in parts:
            idx = parts.index("workspacestorage")
            if idx + 1 < len(db_path.parts):
                return f"cursor-{db_path.parts[idx + 1]}"
        suffix = hashlib.sha1(db_path.as_posix().encode("utf-8")).hexdigest()[:10]
        return f"cursor-{suffix}"
