from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime
from pathlib import Path

from searchat.config import Config, PathResolver
from searchat.models import ConversationRecord, MessageRecord


class ClaudeConnector:
    name = "claude"
    supported_extensions = (".jsonl",)

    def discover_files(self, config: Config) -> list[Path]:
        files: list[Path] = []
        seen: set[Path] = set()
        for claude_dir in PathResolver.resolve_claude_dirs(config):
            if not claude_dir.exists():
                continue
            for json_file in claude_dir.rglob("*.jsonl"):
                if json_file in seen:
                    continue
                seen.add(json_file)
                files.append(json_file)
        return files

    def watch_dirs(self, config: Config) -> list[Path]:
        return [p for p in PathResolver.resolve_claude_dirs(config) if p.exists()]

    def watch_stats(self, config: Config) -> dict[str, int]:
        project_count = 0
        for root in self.watch_dirs(config):
            try:
                project_count += sum(1 for p in root.iterdir() if p.is_dir())
            except OSError:
                continue
        return {"projects": project_count}

    def can_parse(self, path: Path) -> bool:
        return path.suffix == ".jsonl"

    def parse(self, path: Path, embedding_id: int) -> ConversationRecord:
        with open(path, "r", encoding="utf-8") as f:
            lines = [json.loads(line) for line in f]

        file_hash = hashlib.sha256(path.read_bytes()).hexdigest()
        conversation_id = path.stem
        project_id = path.parent.name

        def _extract_content(entry: dict) -> str:
            raw = entry.get("message", {})
            raw_content = raw.get("content", raw.get("text", ""))
            if isinstance(raw_content, str):
                return raw_content
            if isinstance(raw_content, list):
                return "\n\n".join(
                    block.get("text", "")
                    for block in raw_content
                    if block.get("type") == "text"
                )
            return ""

        title = "Untitled"
        for entry in lines:
            text = _extract_content(entry).strip()
            if text:
                title = text[:100]
                break

        messages: list[MessageRecord] = []
        full_text_parts: list[str] = []

        for entry in lines:
            msg_type = entry.get("type")
            if msg_type not in ("user", "assistant"):
                continue

            content = _extract_content(entry)

            code_blocks = re.findall(r"```(?:\w+)?\n(.*?)```", content, re.DOTALL)
            has_code = len(code_blocks) > 0

            timestamp_str = entry.get("timestamp")
            timestamp = datetime.fromisoformat(timestamp_str) if timestamp_str else datetime.now()

            messages.append(
                MessageRecord(
                    sequence=len(messages),
                    role=msg_type,
                    content=content,
                    timestamp=timestamp,
                    has_code=has_code,
                    code_blocks=code_blocks,
                )
            )

            full_text_parts.append(content)

        full_text = "\n\n".join(full_text_parts)
        created_at = messages[0].timestamp if messages else datetime.now()
        updated_at = messages[-1].timestamp if messages else datetime.now()

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
