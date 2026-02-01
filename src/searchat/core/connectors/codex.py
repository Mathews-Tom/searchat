from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime
from pathlib import Path

from searchat.config import Config, PathResolver
from searchat.models import ConversationRecord, MessageRecord


class CodexConnector:
    name = "codex"
    supported_extensions = (".jsonl",)

    def discover_files(self, _config: Config) -> list[Path]:
        files: list[Path] = []
        for codex_dir in PathResolver.resolve_codex_dirs(_config):
            sessions_dir = codex_dir / "sessions"
            if sessions_dir.exists():
                files.extend(sessions_dir.rglob("rollout-*.jsonl"))
            history = codex_dir / "history.jsonl"
            if history.exists():
                files.append(history)
        return files

    def watch_dirs(self, _config: Config) -> list[Path]:
        return [p for p in PathResolver.resolve_codex_dirs(_config) if p.exists()]

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
                        return False
                    if "role" in data and ("content" in data or "text" in data):
                        return True
                    return False
        except (json.JSONDecodeError, OSError):
            return False

    def parse(self, path: Path, embedding_id: int) -> ConversationRecord:
        messages: list[MessageRecord] = []
        full_text_parts: list[str] = []
        created_at: datetime | None = None
        updated_at: datetime | None = None

        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                entry = json.loads(line)
                if not isinstance(entry, dict):
                    continue

                role = entry.get("role")
                if role not in ("user", "assistant", "system", "tool"):
                    continue

                content = entry.get("content", entry.get("text", ""))
                if isinstance(content, dict):
                    content = content.get("text") or content.get("content") or ""
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
                    content = "\n\n".join(parts)
                if not isinstance(content, str):
                    content = ""

                timestamp = self._parse_timestamp(
                    entry.get("timestamp")
                    or entry.get("created_at")
                    or entry.get("time")
                    or entry.get("created")
                )
                if timestamp is None:
                    timestamp = datetime.fromtimestamp(path.stat().st_mtime)

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
        conversation_id = path.stem
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
