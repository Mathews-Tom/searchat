from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any

from searchat.config import Config, PathResolver
from searchat.models import ConversationRecord, MessageRecord


class CodexConnector:
    name: str = "codex"
    supported_extensions: tuple[str, ...] = (".jsonl",)

    def discover_files(self, config: Config) -> list[Path]:
        files: list[Path] = []
        for codex_dir in PathResolver.resolve_codex_dirs(config):
            sessions_dir = codex_dir / "sessions"
            if sessions_dir.exists():
                files.extend(sessions_dir.rglob("rollout-*.jsonl"))
            history = codex_dir / "history.jsonl"
            if history.exists():
                files.append(history)
        return files

    def watch_dirs(self, config: Config) -> list[Path]:
        return [p for p in PathResolver.resolve_codex_dirs(config) if p.exists()]

    def can_parse(self, path: Path) -> bool:
        if path.suffix != ".jsonl":
            return False
        if path.name.startswith("rollout-"):
            return True
        try:
            with open(path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    data = json.loads(line)
                    if not isinstance(data, dict):
                        continue
                    if self._extract_session_id(data):
                        return True
                    if self._extract_message(data) is not None:
                        return True
                    event_type = data.get("type")
                    if isinstance(event_type, str) and event_type in {
                        "session_meta",
                        "turn_context",
                        "response_item",
                        "event_msg",
                    }:
                        return True
                    return False
            return False
        except (json.JSONDecodeError, OSError):
            return False

    def parse(self, path: Path, embedding_id: int) -> ConversationRecord:
        messages: list[MessageRecord] = []
        full_text_parts: list[str] = []
        created_at: datetime | None = None
        updated_at: datetime | None = None
        session_id: str | None = None
        fallback_timestamp = datetime.fromtimestamp(path.stat().st_mtime)

        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                entry = json.loads(line)
                if not isinstance(entry, dict):
                    continue

                if session_id is None:
                    session_id = self._extract_session_id(entry)

                extracted = self._extract_message(entry)
                if extracted is None:
                    continue
                role, content, timestamp = extracted

                if timestamp is None:
                    timestamp = fallback_timestamp

                if created_at is None:
                    created_at = timestamp
                updated_at = timestamp

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

                if content:
                    full_text_parts.append(content)

        file_hash = hashlib.sha256(path.read_bytes()).hexdigest()
        conversation_id = session_id or path.stem
        title = self._title_from_messages(messages) or "Untitled Codex Session"

        full_text = "\n\n".join(full_text_parts)

        return ConversationRecord(
            conversation_id=conversation_id,
            project_id="codex",
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

    def _title_from_messages(self, messages: list[MessageRecord]) -> str | None:
        for msg in messages:
            if msg.role == "user" and msg.content.strip():
                return msg.content.strip().splitlines()[0][:100]
        for msg in messages:
            if msg.content.strip():
                return msg.content.strip().splitlines()[0][:100]
        return None

    def _parse_timestamp(self, value: object) -> datetime | None:
        if value is None:
            return None
        if isinstance(value, (int, float)):
            try:
                # Heuristic: ms vs seconds.
                ts = value / 1000 if value > 1e12 else value
                return datetime.fromtimestamp(ts)
            except (OSError, ValueError):
                return None
        if isinstance(value, str) and value.strip():
            raw = value.strip()
            if raw.endswith("Z"):
                raw = raw[:-1] + "+00:00"
            try:
                return datetime.fromisoformat(raw)
            except ValueError:
                return None
        return None

    def _extract_session_id(self, entry: dict[str, Any]) -> str | None:
        if entry.get("type") == "session_meta":
            payload = entry.get("payload")
            if isinstance(payload, dict):
                payload_id = payload.get("id")
                if isinstance(payload_id, str) and payload_id.strip():
                    return payload_id.strip()

        return None

    def _normalize_role(self, value: object) -> str | None:
        if not isinstance(value, str):
            return None
        role = value.strip().lower()
        if role == "developer":
            role = "system"
        if role in ("user", "assistant", "system", "tool"):
            return role
        return None

    def _extract_text(self, value: object) -> str:
        if isinstance(value, str):
            return value.strip()
        if isinstance(value, list):
            parts: list[str] = []
            for item in value:
                text = self._extract_text(item)
                if text:
                    parts.append(text)
            return "\n\n".join(parts)
        if isinstance(value, dict):
            text_value = value.get("text")
            if isinstance(text_value, str) and text_value.strip():
                return text_value.strip()

            content_value = value.get("content")
            if content_value is not None:
                content_text = self._extract_text(content_value)
                if content_text:
                    return content_text

            parts_value = value.get("parts")
            if parts_value is not None:
                parts_text = self._extract_text(parts_value)
                if parts_text:
                    return parts_text

            items_value = value.get("items")
            if items_value is not None:
                items_text = self._extract_text(items_value)
                if items_text:
                    return items_text

            value_value = value.get("value")
            if isinstance(value_value, str) and value_value.strip():
                return value_value.strip()

        return ""

    def _extract_message(self, entry: dict[str, Any]) -> tuple[str, str, datetime | None] | None:
        role = self._normalize_role(entry.get("role"))
        if role:
            content = self._extract_text(entry.get("content", entry.get("text")))
            if content:
                timestamp = self._parse_timestamp(
                    entry.get("timestamp")
                    or entry.get("created_at")
                    or entry.get("time")
                    or entry.get("created")
                    or entry.get("ts")
                )
                return role, content, timestamp

        event_type = entry.get("type")
        payload = entry.get("payload")
        if event_type == "response_item" and isinstance(payload, dict):
            if payload.get("type") == "message":
                payload_role = self._normalize_role(payload.get("role"))
                if payload_role:
                    payload_content = self._extract_text(payload.get("content", payload.get("text")))
                    if payload_content:
                        timestamp = self._parse_timestamp(
                            entry.get("timestamp")
                            or payload.get("timestamp")
                            or payload.get("created_at")
                            or payload.get("time")
                            or payload.get("created")
                        )
                        return payload_role, payload_content, timestamp
            return None

        # Codex command history format: {"session_id": "...", "ts": ..., "text": "..."}
        if isinstance(entry.get("session_id"), str):
            history_text = entry.get("text")
            if isinstance(history_text, str) and history_text.strip():
                history_timestamp = self._parse_timestamp(
                    entry.get("timestamp")
                    or entry.get("ts")
                    or entry.get("time")
                )
                return "user", history_text.strip(), history_timestamp

        return None
