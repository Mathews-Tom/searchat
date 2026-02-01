from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime
from pathlib import Path

from searchat.config import Config, PathResolver
from searchat.models import ConversationRecord, MessageRecord


class OpenCodeConnector:
    name: str = "opencode"
    supported_extensions: tuple[str, ...] = (".json",)

    def discover_files(self, config: Config) -> list[Path]:
        files: list[Path] = []
        for opencode_dir in PathResolver.resolve_opencode_dirs(config):
            storage_session_dir = opencode_dir / "storage" / "session"
            if not storage_session_dir.exists():
                continue
            files.extend(storage_session_dir.glob("*/*.json"))
        return files

    def watch_dirs(self, config: Config) -> list[Path]:
        dirs: list[Path] = []
        for opencode_dir in PathResolver.resolve_opencode_dirs(config):
            storage_dir = opencode_dir / "storage"
            if storage_dir.exists():
                dirs.append(storage_dir)
        return dirs

    def watch_stats(self, config: Config) -> dict[str, int]:
        project_count = 0
        for root in self.watch_dirs(config):
            session_root = root / "session"
            if not session_root.exists():
                continue
            try:
                project_count += sum(1 for p in session_root.iterdir() if p.is_dir())
            except OSError:
                continue
        return {"projects": project_count}

    def can_parse(self, path: Path) -> bool:
        if path.suffix != ".json":
            return False
        if "storage" in path.parts and "session" in path.parts:
            return True
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            return "projectID" in data and "sessionID" in data
        except (json.JSONDecodeError, OSError):
            return False

    def parse(self, path: Path, embedding_id: int) -> ConversationRecord:
        with open(path, "r", encoding="utf-8") as f:
            session = json.load(f)

        file_hash = hashlib.sha256(path.read_bytes()).hexdigest()

        session_id = session.get("id") or session.get("sessionID") or path.stem
        project_id = session.get("projectID", "unknown")
        title = session.get("title") or "Untitled OpenCode Session"

        time_info = session.get("time", {})
        created_at = self._timestamp_ms_to_datetime(time_info.get("created"))
        updated_at = self._timestamp_ms_to_datetime(time_info.get("updated")) or created_at

        data_root = self._resolve_opencode_data_root(path)
        messages = self._load_opencode_messages(data_root, session_id)
        if not messages:
            for alt_root in PathResolver.resolve_opencode_dirs(None):
                if alt_root == data_root:
                    continue
                messages = self._load_opencode_messages(alt_root, session_id)
                if messages:
                    break
        if not messages:
            messages = self._load_opencode_session_messages(session, data_root)

        if title == "Untitled OpenCode Session":
            for msg in messages:
                if msg.content:
                    title = msg.content[:100].replace("\n", " ").strip()
                    break

        full_text_parts = [msg.content for msg in messages if msg.content]
        full_text = "\n\n".join(full_text_parts)

        return ConversationRecord(
            conversation_id=session_id,
            project_id=f"opencode-{project_id}",
            file_path=str(path),
            title=title,
            created_at=created_at or datetime.now(),
            updated_at=updated_at or datetime.now(),
            message_count=len(messages),
            messages=messages,
            full_text=full_text,
            embedding_id=embedding_id,
            file_hash=file_hash,
            indexed_at=datetime.now(),
        )

    def _load_opencode_messages(self, data_root: Path, session_id: str) -> list[MessageRecord]:
        messages_dir = data_root / "storage" / "message" / session_id
        if not messages_dir.exists():
            return []

        raw_messages = []
        for message_file in messages_dir.glob("*.json"):
            try:
                with open(message_file, "r", encoding="utf-8") as f:
                    message = json.load(f)
            except json.JSONDecodeError:
                continue

            role = message.get("role")
            if role not in ("user", "assistant"):
                continue

            content = self._extract_opencode_message_text(data_root, message)
            if not content:
                continue

            created_at = self._timestamp_ms_to_datetime(message.get("time", {}).get("created"))
            raw_messages.append((created_at, message_file.name, role, content))

        raw_messages.sort(key=lambda item: (item[0] or datetime.min, item[1]))

        messages: list[MessageRecord] = []
        for sequence, (created_at, _name, role, content) in enumerate(raw_messages):
            code_blocks = re.findall(r"```(?:\w+)?\n(.*?)```", content, re.DOTALL)
            has_code = len(code_blocks) > 0
            messages.append(
                MessageRecord(
                    sequence=sequence,
                    role=role,
                    content=content,
                    timestamp=created_at or datetime.now(),
                    has_code=has_code,
                    code_blocks=code_blocks,
                )
            )

        return messages

    def _load_opencode_session_messages(self, session: dict, data_root: Path) -> list[MessageRecord]:
        session_messages = session.get("messages")
        if not isinstance(session_messages, list):
            return []

        raw_messages = []
        for index, entry in enumerate(session_messages):
            if not isinstance(entry, dict):
                continue
            role = entry.get("role") or entry.get("type")
            if role not in ("user", "assistant"):
                continue
            content = self._extract_opencode_message_text(data_root, entry)
            if not content:
                continue
            created_at = self._timestamp_ms_to_datetime(entry.get("time", {}).get("created"))
            raw_messages.append((created_at, f"{index:06d}", role, content))

        raw_messages.sort(key=lambda item: (item[0] or datetime.min, item[1]))

        messages: list[MessageRecord] = []
        for sequence, (created_at, _name, role, content) in enumerate(raw_messages):
            code_blocks = re.findall(r"```(?:\w+)?\n(.*?)```", content, re.DOTALL)
            has_code = len(code_blocks) > 0
            messages.append(
                MessageRecord(
                    sequence=sequence,
                    role=role,
                    content=content,
                    timestamp=created_at or datetime.now(),
                    has_code=has_code,
                    code_blocks=code_blocks,
                )
            )

        return messages

    def _extract_opencode_message_text(self, data_root: Path, message: dict) -> str:
        def _normalize_text(value: object) -> str:
            if isinstance(value, str) and value.strip():
                return value.strip()
            if isinstance(value, dict):
                text = value.get("text") or value.get("content") or value.get("value")
                if isinstance(text, str) and text.strip():
                    return text.strip()
            if isinstance(value, list):
                parts = []
                for block in value:
                    if not isinstance(block, dict):
                        continue
                    text = block.get("text") or block.get("content") or block.get("value")
                    if isinstance(text, str) and text.strip():
                        parts.append(text.strip())
                if parts:
                    return "\n\n".join(parts)
            return ""

        content_text = _normalize_text(message.get("content"))
        if content_text:
            return content_text

        text_text = _normalize_text(message.get("text"))
        if text_text:
            return text_text

        message_text = _normalize_text(message.get("message"))
        if message_text:
            return message_text

        message_id = message.get("id")
        if isinstance(message_id, str):
            parts_text = self._load_opencode_parts_text(data_root, message_id)
            if parts_text:
                return parts_text

        summary = message.get("summary")
        if isinstance(summary, dict):
            body = summary.get("body")
            if isinstance(body, str) and body.strip():
                return body.strip()

            title = summary.get("title")
            if isinstance(title, str) and title.strip():
                return title.strip()

        return ""

    def _load_opencode_parts_text(self, data_root: Path, message_id: str) -> str:
        parts_dir = data_root / "storage" / "part" / message_id
        if not parts_dir.exists():
            return ""

        parts = []
        for part_file in sorted(parts_dir.glob("*.json")):
            try:
                with open(part_file, "r", encoding="utf-8") as f:
                    part = json.load(f)
            except json.JSONDecodeError:
                continue

            text = part.get("text")
            if isinstance(text, str) and text.strip():
                parts.append(text.strip())
                continue

            state = part.get("state")
            if isinstance(state, dict):
                output = state.get("output")
                if isinstance(output, str) and output.strip():
                    parts.append(output.strip())

        return "\n\n".join(parts)

    def _resolve_opencode_data_root(self, session_path: Path) -> Path:
        if "storage" in session_path.parts:
            storage_index = session_path.parts.index("storage")
            return Path(*session_path.parts[:storage_index])
        if len(session_path.parents) >= 4:
            return session_path.parents[3]
        return session_path.parent

    def _timestamp_ms_to_datetime(self, value: int | None) -> datetime | None:
        if value is None:
            return None
        try:
            return datetime.fromtimestamp(value / 1000)
        except (OSError, ValueError, TypeError):
            return None
