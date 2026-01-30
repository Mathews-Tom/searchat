from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime
from pathlib import Path

from searchat.config import Config, PathResolver
from searchat.models import ConversationRecord, MessageRecord


class VibeConnector:
    name = "vibe"
    supported_extensions = (".json",)

    def discover_files(self, _config: Config) -> list[Path]:
        files: list[Path] = []
        for vibe_dir in PathResolver.resolve_vibe_dirs():
            if not vibe_dir.exists():
                continue
            files.extend(vibe_dir.glob("*.json"))
        return files

    def watch_dirs(self, _config: Config) -> list[Path]:
        return [p for p in PathResolver.resolve_vibe_dirs() if p.exists()]

    def watch_stats(self, _config: Config) -> dict[str, int]:
        session_count = 0
        for root in self.watch_dirs(_config):
            try:
                session_count += sum(1 for p in root.glob("*.json") if p.is_file())
            except OSError:
                continue
        return {"sessions": session_count}

    def can_parse(self, path: Path) -> bool:
        if path.suffix != ".json":
            return False
        if ".vibe" in str(path):
            return True
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            return "metadata" in data and "messages" in data
        except (json.JSONDecodeError, OSError):
            return False

    def parse(self, path: Path, embedding_id: int) -> ConversationRecord:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)

        file_hash = hashlib.sha256(path.read_bytes()).hexdigest()
        metadata = data.get("metadata", {})
        session_id = metadata.get("session_id", path.stem)

        env = metadata.get("environment", {})
        working_dir = env.get("working_directory", "")
        project_id = Path(working_dir).name if working_dir else "vibe-session"

        start_time_str = metadata.get("start_time")
        end_time_str = metadata.get("end_time")
        created_at = datetime.fromisoformat(start_time_str) if start_time_str else datetime.now()
        updated_at = datetime.fromisoformat(end_time_str) if end_time_str else created_at

        messages: list[MessageRecord] = []
        full_text_parts: list[str] = []
        title = "Untitled Vibe Session"

        for msg in data.get("messages", []):
            role = msg.get("role")
            if role not in ("user", "assistant"):
                continue

            content = msg.get("content", "")
            if not content:
                continue

            if role == "user" and title == "Untitled Vibe Session":
                title = content[:100].replace("\n", " ").strip()

            code_blocks = re.findall(r"```(?:\w+)?\n(.*?)```", content, re.DOTALL)
            has_code = len(code_blocks) > 0

            messages.append(
                MessageRecord(
                    sequence=len(messages),
                    role=role,
                    content=content,
                    timestamp=created_at,
                    has_code=has_code,
                    code_blocks=code_blocks,
                )
            )

            full_text_parts.append(content)

        full_text = "\n\n".join(full_text_parts)

        return ConversationRecord(
            conversation_id=session_id,
            project_id=f"vibe-{project_id}",
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
