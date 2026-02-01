from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime
from pathlib import Path

from searchat.config import Config, PathResolver
from searchat.models import ConversationRecord, MessageRecord


class GeminiCLIConnector:
    name = "gemini"
    supported_extensions = (".json",)

    def discover_files(self, _config: Config) -> list[Path]:
        files: list[Path] = []
        for gemini_root in PathResolver.resolve_gemini_dirs(_config):
            if not gemini_root.exists():
                continue
            for project_dir in gemini_root.iterdir():
                if not project_dir.is_dir():
                    continue
                chats_dir = project_dir / "chats"
                if chats_dir.exists():
                    files.extend(chats_dir.glob("*.json"))
        return files

    def watch_dirs(self, _config: Config) -> list[Path]:
        return [p for p in PathResolver.resolve_gemini_dirs(_config) if p.exists()]

    def can_parse(self, path: Path) -> bool:
        if path.suffix != ".json":
            return False
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except (json.JSONDecodeError, OSError):
            return False

        if not isinstance(data, dict):
            return False

        # Avoid collisions with other JSON connectors.
        if "metadata" in data and "messages" in data:
            return False
        if "projectID" in data and "sessionID" in data:
            return False

        history = data.get("history") or data.get("turns")
        if isinstance(history, list) and history:
            return True

        messages = data.get("messages")
        if isinstance(messages, list) and messages:
            return True

        return False

    def parse(self, path: Path, embedding_id: int) -> ConversationRecord:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)

        if not isinstance(data, dict):
            raise ValueError(f"Invalid Gemini chat format: {path}")

        items = data.get("history") or data.get("turns") or data.get("messages") or []
        if not isinstance(items, list):
            items = []

        messages: list[MessageRecord] = []
        full_text_parts: list[str] = []

        for entry in items:
            if not isinstance(entry, dict):
                continue

            role = entry.get("role") or entry.get("author") or "user"
            if not isinstance(role, str):
                role = "user"
            role = role.lower()
            if role not in ("user", "assistant", "system", "tool"):
                continue

            content = self._extract_content(entry)
            if not content:
                continue

            timestamp = self._parse_timestamp(entry.get("timestamp") or entry.get("createdAt") or entry.get("time"))
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
        conversation_id = path.stem

        project_hash = self._project_hash_from_path(path)
        project_id = f"gemini-{project_hash}" if project_hash else "gemini"

        title = self._title_from_messages(messages) or "Untitled Gemini Chat"
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

        parts = entry.get("parts")
        if isinstance(parts, list):
            out: list[str] = []
            for part in parts:
                if isinstance(part, str) and part.strip():
                    out.append(part.strip())
                    continue
                if isinstance(part, dict):
                    text = part.get("text") or part.get("content")
                    if isinstance(text, str) and text.strip():
                        out.append(text.strip())
            return "\n\n".join(out)

        return ""

    def _project_hash_from_path(self, path: Path) -> str | None:
        # ~/.gemini/tmp/<project_hash>/chats/<id>.json
        try:
            if path.parent.name == "chats":
                return path.parent.parent.name
        except Exception:
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
