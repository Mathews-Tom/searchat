from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime
from pathlib import Path

from searchat.config import Config, PathResolver
from searchat.models import ConversationRecord, MessageRecord


class ContinueConnector:
    name: str = "continue"
    supported_extensions: tuple[str, ...] = (".json",)

    def discover_files(self, config: Config) -> list[Path]:
        files: list[Path] = []
        for sessions_dir in PathResolver.resolve_continue_dirs(config):
            if not sessions_dir.exists():
                continue
            for candidate in sessions_dir.glob("*.json"):
                if candidate.name == "sessions.json":
                    continue
                files.append(candidate)
        return files

    def watch_dirs(self, config: Config) -> list[Path]:
        return [p for p in PathResolver.resolve_continue_dirs(config) if p.exists()]

    def can_parse(self, path: Path) -> bool:
        if path.suffix != ".json":
            return False
        if path.name == "sessions.json":
            return False

        normalized = str(path).lower().replace("\\", "/")
        likely_continue = ("/.continue/" in normalized) and ("/sessions/" in normalized)

        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except (json.JSONDecodeError, OSError):
            return False

        if not isinstance(data, dict):
            return False

        items = data.get("history") or data.get("messages")
        if not isinstance(items, list) or not items:
            return False

        def candidate_message(entry: object) -> dict | None:
            if not isinstance(entry, dict):
                return None
            inner = entry.get("message")
            if isinstance(inner, dict):
                return inner
            return entry

        for entry in items[:10]:
            msg = candidate_message(entry)
            if not isinstance(msg, dict):
                continue
            role = msg.get("role") or msg.get("author")
            content = msg.get("content") or msg.get("text") or msg.get("message")
            if isinstance(role, str) and role.strip() and (
                (isinstance(content, str) and content.strip()) or isinstance(content, (list, dict))
            ):
                return True

        # If the file lives under Continue's sessions dir, accept it once it looks vaguely session-like.
        return bool(likely_continue)

    def parse(self, path: Path, embedding_id: int) -> ConversationRecord:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)

        if not isinstance(data, dict):
            raise ValueError(f"Invalid Continue session format: {path}")

        items = data.get("history") or data.get("messages") or []
        if not isinstance(items, list):
            items = []

        workspace_dir = data.get("workspaceDirectory")
        workspace_hash = self._workspace_hash(workspace_dir)
        project_id = f"continue-{workspace_hash}" if workspace_hash else "continue"

        messages: list[MessageRecord] = []
        full_text_parts: list[str] = []

        for entry in items:
            if not isinstance(entry, dict):
                continue

            inner = entry.get("message")
            msg_obj: dict
            if isinstance(inner, dict):
                msg_obj = inner
            else:
                msg_obj = entry

            role = msg_obj.get("role") or msg_obj.get("author") or "user"
            if not isinstance(role, str):
                role = "user"
            role = role.lower().strip()
            if role not in ("user", "assistant", "system", "tool"):
                continue

            content = self._extract_content(msg_obj)
            if not content:
                continue

            timestamp = self._parse_timestamp(
                entry.get("timestamp")
                or entry.get("createdAt")
                or entry.get("time")
                or msg_obj.get("timestamp")
                or msg_obj.get("createdAt")
                or msg_obj.get("time")
            )
            if timestamp is None:
                timestamp = datetime.fromtimestamp(path.stat().st_mtime)

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

        file_hash = hashlib.sha256(path.read_bytes()).hexdigest()
        conversation_id = (
            data.get("sessionId")
            or data.get("sessionID")
            or data.get("id")
            or path.stem
        )
        if not isinstance(conversation_id, str) or not conversation_id.strip():
            conversation_id = path.stem
        raw_title = data.get("title")
        title: str | None = None
        if isinstance(raw_title, str):
            candidate = raw_title.strip()
            if candidate and re.search(r"[A-Za-z0-9]", candidate) and len(candidate) >= 4:
                title = candidate
        title = title or (self._title_from_messages(messages) or "Untitled Continue Session")
        full_text = "\n\n".join(full_text_parts)

        created_at = messages[0].timestamp if messages else datetime.fromtimestamp(path.stat().st_mtime)
        updated_at = messages[-1].timestamp if messages else datetime.fromtimestamp(path.stat().st_mtime)

        return ConversationRecord(
            conversation_id=conversation_id,
            project_id=project_id,
            file_path=str(path),
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

    def _extract_content(self, entry: dict) -> str:
        content = entry.get("content") or entry.get("text") or entry.get("message")
        if isinstance(content, str) and content.strip():
            return content.strip()
        if isinstance(content, dict):
            text = content.get("text") or content.get("content")
            if isinstance(text, str) and text.strip():
                return text.strip()
        if isinstance(content, list):
            parts: list[str] = []
            for block in content:
                if isinstance(block, str) and block.strip():
                    parts.append(block.strip())
                    continue
                if isinstance(block, dict):
                    text = block.get("text") or block.get("content")
                    if isinstance(text, str) and text.strip():
                        parts.append(text.strip())
            if parts:
                return "\n\n".join(parts)
        return ""

    def _title_from_messages(self, messages: list[MessageRecord]) -> str | None:
        for msg in messages:
            if msg.role == "user" and msg.content.strip():
                return msg.content.strip().splitlines()[0][:100]
        for msg in messages:
            if msg.content.strip():
                return msg.content.strip().splitlines()[0][:100]
        return None

    def _workspace_hash(self, value: object) -> str | None:
        if not isinstance(value, str) or not value.strip():
            return None
        digest = hashlib.sha1(value.strip().encode("utf-8")).hexdigest()
        return digest[:10]

    def _parse_timestamp(self, value: object) -> datetime | None:
        if value is None:
            return None
        if isinstance(value, (int, float)):
            try:
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
