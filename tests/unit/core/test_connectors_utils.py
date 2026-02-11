"""Tests for searchat.core.connectors.utils."""
from __future__ import annotations

from datetime import datetime

import pytest

from searchat.core.connectors.utils import (
    MARKDOWN_CODE_BLOCK_RE,
    title_from_messages,
    parse_flexible_timestamp,
)
from searchat.models import MessageRecord


def _msg(role: str, content: str) -> MessageRecord:
    """Create a minimal MessageRecord."""
    return MessageRecord(
        sequence=0,
        role=role,
        content=content,
        timestamp=datetime(2025, 1, 15),
        has_code=False,
    )


class TestMarkdownCodeBlockRe:
    """Tests for MARKDOWN_CODE_BLOCK_RE compiled regex."""

    def test_matches_fenced_block(self):
        text = "text\n```python\ncode here\n```\nmore text"
        matches = MARKDOWN_CODE_BLOCK_RE.findall(text)
        assert len(matches) == 1
        assert "code here" in matches[0]

    def test_no_match_without_fence(self):
        text = "plain text without code"
        assert MARKDOWN_CODE_BLOCK_RE.findall(text) == []


class TestTitleFromMessages:
    """Tests for title_from_messages."""

    def test_first_user_message(self):
        messages = [
            _msg("assistant", "Hello!"),
            _msg("user", "How do I install Python?"),
        ]
        assert title_from_messages(messages) == "How do I install Python?"

    def test_fallback_to_any_role(self):
        messages = [_msg("assistant", "Welcome to the chat.")]
        assert title_from_messages(messages) == "Welcome to the chat."

    def test_all_empty_returns_none(self):
        messages = [_msg("user", ""), _msg("assistant", "  ")]
        assert title_from_messages(messages) is None

    def test_truncates_to_100_chars(self):
        long_text = "a" * 200
        messages = [_msg("user", long_text)]
        result = title_from_messages(messages)
        assert result is not None
        assert len(result) == 100

    def test_takes_first_line_only(self):
        messages = [_msg("user", "First line\nSecond line")]
        assert title_from_messages(messages) == "First line"

    def test_empty_list(self):
        assert title_from_messages([]) is None


class TestParseFlexibleTimestamp:
    """Tests for parse_flexible_timestamp."""

    def test_none_input(self):
        assert parse_flexible_timestamp(None) is None

    def test_iso_string(self):
        result = parse_flexible_timestamp("2025-01-15T10:30:00")
        assert isinstance(result, datetime)
        assert result.year == 2025
        assert result.month == 1

    def test_iso_string_with_z(self):
        result = parse_flexible_timestamp("2025-01-15T10:30:00Z")
        assert isinstance(result, datetime)
        assert result.tzinfo is not None

    def test_epoch_seconds(self):
        result = parse_flexible_timestamp(1705312200.0)
        assert isinstance(result, datetime)

    def test_epoch_milliseconds(self):
        result = parse_flexible_timestamp(1705312200000)
        assert isinstance(result, datetime)

    def test_empty_string(self):
        assert parse_flexible_timestamp("") is None

    def test_whitespace_only(self):
        assert parse_flexible_timestamp("   ") is None

    def test_invalid_string(self):
        assert parse_flexible_timestamp("not-a-date") is None

    def test_invalid_numeric(self):
        # Extremely large value that causes OSError
        assert parse_flexible_timestamp(1e20) is None

    def test_non_string_non_numeric(self):
        assert parse_flexible_timestamp([1, 2, 3]) is None

    def test_integer_epoch(self):
        result = parse_flexible_timestamp(1705312200)
        assert isinstance(result, datetime)
