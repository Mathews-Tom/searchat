from __future__ import annotations

import hashlib
import re
from datetime import datetime
from pathlib import Path

from searchat.config import Config, PathResolver
from searchat.models import ConversationRecord, MessageRecord


class AiderConnector:
    name: str = "aider"
    supported_extensions: tuple[str, ...] = (".md",)

    _HISTORY_FILENAME = ".aider.chat.history.md"
    _MAX_DISCOVERED_FILES = 500

    def discover_files(self, config: Config) -> list[Path]:
        roots = PathResolver.resolve_aider_dirs(config)
        files: list[Path] = []
        seen: set[str] = set()

        def _add(candidate: Path) -> None:
            key = str(candidate.resolve()) if candidate.exists() else str(candidate)
            if key in seen:
                return
            seen.add(key)
            files.append(candidate)

        for root in roots:
            if len(files) >= self._MAX_DISCOVERED_FILES:
                break

            if root.is_file():
                if self.can_parse(root):
                    _add(root)
                continue

            if not root.exists() or not root.is_dir():
                continue

            direct = root / self._HISTORY_FILENAME
            if direct.exists():
                _add(direct)
                if len(files) >= self._MAX_DISCOVERED_FILES:
                    break

            for candidate in root.rglob(self._HISTORY_FILENAME):
                _add(candidate)
                if len(files) >= self._MAX_DISCOVERED_FILES:
                    break

        return files

    def watch_dirs(self, config: Config) -> list[Path]:
        return [p for p in PathResolver.resolve_aider_dirs(config) if p.exists()]

    def can_parse(self, path: Path) -> bool:
        return path.name == self._HISTORY_FILENAME and path.suffix == ".md"

    def parse(self, path: Path, embedding_id: int) -> ConversationRecord:
        text = path.read_text(encoding="utf-8")
        file_hash = hashlib.sha256(path.read_bytes()).hexdigest()

        conversation_id = self._conversation_id_for_path(path)
        project_id = f"aider-{path.parent.name}" if path.parent.name else "aider"

        created_at = datetime.fromtimestamp(path.stat().st_mtime)
        updated_at = created_at

        messages = self._parse_messages(text, base_timestamp=created_at)
        title = self._title_from_messages(messages) or "Untitled Aider Chat"

        full_text_parts = [m.content for m in messages if m.content]
        full_text = "\n\n".join(full_text_parts)

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

    def _conversation_id_for_path(self, path: Path) -> str:
        raw = str(path.resolve()) if path.exists() else str(path)
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]

    def _parse_messages(self, text: str, base_timestamp: datetime) -> list[MessageRecord]:
        # Common formats seen in `.aider.chat.history.md` vary by version and user config.
        # We support a small set of explicit, low-false-positive delimiters.
        header_patterns: list[re.Pattern[str]] = [
            re.compile(r"^\s{0,3}#{1,6}\s*(user|assistant|system)\s*:?\s*$", re.IGNORECASE),
            re.compile(r"^\s{0,3}(user|assistant|system)\s*:\s*$", re.IGNORECASE),
        ]
        inline_blockquote = re.compile(r"^\s{0,3}>\s*(user|assistant|system)\s*:\s*(.*)$", re.IGNORECASE)

        messages: list[MessageRecord] = []
        current_role: str | None = None
        current_lines: list[str] = []
        found_delimiter = False

        def _flush() -> None:
            nonlocal current_role, current_lines
            if current_role is None:
                current_lines = []
                return
            content = "\n".join(current_lines).strip("\n")
            if not content.strip():
                current_lines = []
                return
            code_blocks = re.findall(r"```(?:\w+)?\n(.*?)```", content, re.DOTALL)
            messages.append(
                MessageRecord(
                    sequence=len(messages),
                    role=current_role,
                    content=content,
                    timestamp=base_timestamp,
                    has_code=len(code_blocks) > 0,
                    code_blocks=code_blocks,
                )
            )
            current_lines = []

        for line in text.splitlines():
            m_inline = inline_blockquote.match(line)
            if m_inline:
                found_delimiter = True
                _flush()
                current_role = m_inline.group(1).lower()
                inline = (m_inline.group(2) or "").rstrip()
                current_lines = [inline] if inline else []
                continue

            matched_header = False
            for pattern in header_patterns:
                m = pattern.match(line)
                if m:
                    found_delimiter = True
                    _flush()
                    current_role = m.group(1).lower()
                    matched_header = True
                    break
            if matched_header:
                continue

            current_lines.append(line)

        _flush()

        if not found_delimiter:
            content = text.strip()
            if content:
                code_blocks = re.findall(r"```(?:\w+)?\n(.*?)```", content, re.DOTALL)
                return [
                    MessageRecord(
                        sequence=0,
                        role="user",
                        content=content,
                        timestamp=base_timestamp,
                        has_code=len(code_blocks) > 0,
                        code_blocks=code_blocks,
                    )
                ]

        if not messages:
            raise ValueError("No messages parsed from Aider history")

        return messages

    def _title_from_messages(self, messages: list[MessageRecord]) -> str | None:
        for msg in messages:
            if msg.role == "user" and msg.content.strip():
                return msg.content.strip().splitlines()[0][:100]
        for msg in messages:
            if msg.content.strip():
                return msg.content.strip().splitlines()[0][:100]
        return None
