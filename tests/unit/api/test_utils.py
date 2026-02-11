"""Tests for searchat.api.utils."""
from __future__ import annotations

from datetime import datetime

from searchat.api.utils import detect_tool_from_path, detect_source_from_path, parse_date_filter


class TestDetectToolFromPath:
    """Tests for detect_tool_from_path."""

    def test_opencode(self):
        assert detect_tool_from_path("/home/user/.local/share/opencode/conv.json") == "opencode"

    def test_codex(self):
        assert detect_tool_from_path("/home/user/.codex/sessions/abc.jsonl") == "codex"

    def test_continue(self):
        assert detect_tool_from_path("/home/user/.continue/sessions/s1.json") == "continue"

    def test_cursor(self):
        assert detect_tool_from_path("/data/.vscdb.cursor/conv.json") == "cursor"

    def test_gemini(self):
        assert detect_tool_from_path("/home/user/.gemini/tmp/abc/chats/c1.json") == "gemini"

    def test_aider(self):
        assert detect_tool_from_path("/project/.aider.chat.history.md") == "aider"

    def test_claude_jsonl(self):
        assert detect_tool_from_path("/home/user/.claude/projects/conv.jsonl") == "claude"

    def test_vibe(self):
        assert detect_tool_from_path("/home/user/.vibe/sessions/s1.json") == "vibe"

    def test_plain_jsonl_defaults_claude(self):
        assert detect_tool_from_path("/some/path/chat.jsonl") == "claude"

    def test_unknown_defaults_vibe(self):
        assert detect_tool_from_path("/some/path/file.txt") == "vibe"


class TestDetectSourceFromPath:
    """Tests for detect_source_from_path."""

    def test_wsl_home(self):
        assert detect_source_from_path("/home/user/.claude/conv.jsonl") == "WSL"

    def test_wsl_keyword(self):
        assert detect_source_from_path("/mnt/wsl/data/conv.jsonl") == "WSL"

    def test_windows(self):
        assert detect_source_from_path("C:\\Users\\test\\.claude\\conv.jsonl") == "WIN"


class TestParseDateFilter:
    """Tests for parse_date_filter."""

    def test_no_preset(self):
        result_from, result_to = parse_date_filter(None, None, None)
        assert result_from is None
        assert result_to is None

    def test_custom_both(self):
        result_from, result_to = parse_date_filter("custom", "2025-01-01", "2025-01-31")
        assert result_from == datetime(2025, 1, 1)
        assert result_to is not None
        assert result_to.day == 1
        assert result_to.month == 2

    def test_custom_from_only(self):
        result_from, result_to = parse_date_filter("custom", "2025-06-01", None)
        assert result_from == datetime(2025, 6, 1)
        assert result_to is None

    def test_today(self):
        result_from, result_to = parse_date_filter("today", None, None)
        assert result_from is not None
        assert result_to is not None
        assert result_from.hour == 0
        assert result_from.minute == 0

    def test_week(self):
        result_from, result_to = parse_date_filter("week", None, None)
        assert result_from is not None
        assert result_to is not None

    def test_month(self):
        result_from, result_to = parse_date_filter("month", None, None)
        assert result_from is not None
        assert result_to is not None
