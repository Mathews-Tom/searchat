"""Shared utilities used by multiple conversation connectors."""
from __future__ import annotations

import re
from datetime import datetime

from searchat.models import MessageRecord

# Markdown fenced code block pattern (matches ```lang\n...\n```).
MARKDOWN_CODE_BLOCK_RE: re.Pattern[str] = re.compile(
    r"```(?:\w+)?\n(.*?)```", re.DOTALL,
)


def title_from_messages(messages: list[MessageRecord]) -> str | None:
    """Derive a conversation title from the first meaningful user message.

    Falls back to the first non-empty message of any role if no user
    message is available.  Returns ``None`` when all messages are empty.
    """
    for msg in messages:
        if msg.role == "user" and msg.content.strip():
            return msg.content.strip().splitlines()[0][:100]
    for msg in messages:
        if msg.content.strip():
            return msg.content.strip().splitlines()[0][:100]
    return None


def parse_flexible_timestamp(value: object) -> datetime | None:
    """Parse a timestamp from various formats.

    Handles:
    - Numeric values (epoch seconds or milliseconds, auto-detected via
      the ``> 1e12`` heuristic).
    - ISO 8601 strings, including trailing ``Z`` (UTC marker).

    Returns ``None`` when *value* is ``None``, empty, or unparseable.
    """
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
