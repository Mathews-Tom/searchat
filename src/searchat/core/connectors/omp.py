from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any

from searchat.config import Config, PathResolver
from searchat.core.connectors.base import AgentProviderBase
from searchat.core.connectors.utils import (
    MARKDOWN_CODE_BLOCK_RE,
    parse_flexible_timestamp,
    title_from_messages,
)
from searchat.core.logging_config import get_logger
from searchat.models import ConversationRecord, MessageRecord

logger = get_logger(__name__)

# omp session files are named `<ISO8601-with-dashes>Z_<uuid>.jsonl`, e.g.
# `2026-06-04T22-25-47-929Z_019e94be-1d99-7000-9ee7-c208ddf9d5ec.jsonl`, and live
# directly under a per-cwd slug directory: `sessions/<cwd-slug>/<file>.jsonl`.
# Per-tool-call logs and subagent transcripts live one level deeper, inside a
# same-named companion directory (`sessions/<cwd-slug>/<file>/*.log`, occasional
# `*.jsonl`) and never match this filename pattern -- keeping that noise out of
# both discovery and the watcher's `detect_connector` filter without needing to
# inspect file contents or directory depth.
_SESSION_FILENAME_RE = re.compile(
    r"^\d{4}-\d{2}-\d{2}T\d{2}-\d{2}-\d{2}-\d{3}Z_"
    r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\.jsonl$"
)

# omp message roles this connector treats as conversation content, normalized
# to Searchat's role vocabulary (mirrors CodexConnector._normalize_role, which
# maps "developer" -> "system" and accepts a "tool" role).
_ROLE_MAP = {
    "user": "user",
    "assistant": "assistant",
    "developer": "system",
    "toolresult": "tool",
    "bashexecution": "tool",
}


class OmpConnector(AgentProviderBase):
    name: str = "omp"
    supported_extensions: tuple[str, ...] = (".jsonl",)

    def discover_files(self, config: Config) -> list[Path]:
        files: list[Path] = []
        for root in PathResolver.resolve_omp_dirs(config):
            if not root.exists():
                continue
            for path in root.glob("*/*.jsonl"):
                if _SESSION_FILENAME_RE.match(path.name):
                    files.append(path)
        return files

    def watch_dirs(self, config: Config) -> list[Path]:
        return [p for p in PathResolver.resolve_omp_dirs(config) if p.exists()]

    def can_parse(self, path: Path) -> bool:
        return path.suffix == ".jsonl" and bool(_SESSION_FILENAME_RE.match(path.name))

    @staticmethod
    def _normalize_role(value: object) -> str | None:
        if not isinstance(value, str):
            return None
        return _ROLE_MAP.get(value.strip().lower())

    @staticmethod
    def _extract_text(content: object) -> str:
        """Concatenate `text`-type content blocks; skip thinking/toolCall/image."""
        if isinstance(content, str):
            return content.strip()
        if not isinstance(content, list):
            return ""
        parts: list[str] = []
        for block in content:
            if isinstance(block, dict) and block.get("type") == "text":
                text = block.get("text")
                if isinstance(text, str) and text.strip():
                    parts.append(text.strip())
        return "\n\n".join(parts)

    def _iter_entries(self, path: Path) -> list[dict[str, Any]]:
        """Parse each JSONL line, skipping and logging malformed ones.

        omp rewrites some lines in place (e.g. padded `title` events), so a
        line read mid-write can be truncated or invalid JSON; that must not
        fail the whole file.
        """
        entries: list[dict[str, Any]] = []
        with open(path, "r", encoding="utf-8") as f:
            for line_no, raw_line in enumerate(f, start=1):
                line = raw_line.strip()
                if not line:
                    continue
                try:
                    entry = json.loads(line)
                except json.JSONDecodeError as exc:
                    logger.warning("Skipping malformed line %d in %s: %s", line_no, path, exc)
                    continue
                if isinstance(entry, dict):
                    entries.append(entry)
        return entries

    def parse(self, path: Path, embedding_id: int) -> ConversationRecord:
        entries = self._iter_entries(path)
        fallback_timestamp = datetime.fromtimestamp(path.stat().st_mtime)

        session_id: str | None = None
        session_title: str | None = None
        messages: list[MessageRecord] = []
        full_text_parts: list[str] = []
        created_at: datetime | None = None
        updated_at: datetime | None = None

        for entry in entries:
            if entry.get("type") == "session":
                if session_id is None and isinstance(entry.get("id"), str):
                    session_id = entry["id"]
                if session_title is None and isinstance(entry.get("title"), str) and entry["title"].strip():
                    session_title = entry["title"].strip()
                continue

            if entry.get("type") != "message":
                continue

            message = entry.get("message")
            if not isinstance(message, dict):
                continue

            role = self._normalize_role(message.get("role"))
            if role is None:
                continue

            content = self._extract_text(message.get("content"))
            if not content:
                continue

            timestamp = (
                parse_flexible_timestamp(message.get("timestamp"))
                or parse_flexible_timestamp(entry.get("timestamp"))
                or fallback_timestamp
            )

            if created_at is None:
                created_at = timestamp
            updated_at = timestamp

            code_blocks = MARKDOWN_CODE_BLOCK_RE.findall(content)
            messages.append(
                MessageRecord(
                    sequence=len(messages),
                    role=role,
                    content=content,
                    timestamp=timestamp,
                    has_code=len(code_blocks) > 0,
                    code_blocks=code_blocks,
                )
            )
            full_text_parts.append(content)

        file_hash = hashlib.sha256(path.read_bytes()).hexdigest()
        conversation_id = session_id or path.stem
        title = session_title or title_from_messages(messages) or "Untitled omp Session"

        return ConversationRecord(
            conversation_id=conversation_id,
            project_id=path.parent.name,
            file_path=str(path),
            title=title,
            created_at=created_at or fallback_timestamp,
            updated_at=updated_at or fallback_timestamp,
            message_count=len(messages),
            messages=messages,
            full_text="\n\n".join(full_text_parts),
            embedding_id=embedding_id,
            file_hash=file_hash,
            indexed_at=datetime.now(),
        )

    # -- V2: AgentProvider methods --

    def load_messages(self, path: Path) -> list[dict[str, Any]]:
        messages: list[dict[str, Any]] = []
        for entry in self._iter_entries(path):
            if entry.get("type") != "message":
                continue
            message = entry.get("message")
            if not isinstance(message, dict):
                continue
            role = self._normalize_role(message.get("role"))
            if role is None:
                continue
            content = self._extract_text(message.get("content"))
            if content:
                messages.append({"role": role, "content": content})
        return messages

    def extract_cwd(self, path: Path) -> str | None:
        for entry in self._iter_entries(path):
            if entry.get("type") == "session":
                cwd = entry.get("cwd")
                if isinstance(cwd, str) and cwd.strip():
                    return cwd.strip()
        return None

    def build_resume_command(self, path: Path) -> str | None:
        for entry in self._iter_entries(path):
            if entry.get("type") == "session":
                session_id = entry.get("id")
                if isinstance(session_id, str) and session_id.strip():
                    return f"omp --resume {session_id.strip()}"
        return None
