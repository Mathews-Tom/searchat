"""Tests for searchat.core.filters.tool_sql_conditions."""
from __future__ import annotations

import pytest

from searchat.core.filters import tool_sql_conditions


class TestToolSqlConditions:
    """Tests for tool_sql_conditions."""

    def test_claude_returns_exclusion_conditions(self):
        conditions = tool_sql_conditions("claude")
        assert len(conditions) > 0
        assert all("NOT LIKE" in c or "!=" in c for c in conditions)

    def test_claude_with_prefix(self):
        conditions = tool_sql_conditions("claude", prefix="c")
        assert all(c.startswith("c.") for c in conditions)

    def test_single_condition_tool(self):
        conditions = tool_sql_conditions("vibe")
        assert len(conditions) == 1
        assert "vibe" in conditions[0]

    def test_multi_condition_tool(self):
        conditions = tool_sql_conditions("codex")
        assert len(conditions) == 1
        assert "OR" in conditions[0]

    def test_gemini_multi_condition(self):
        conditions = tool_sql_conditions("gemini")
        assert len(conditions) == 1
        assert "OR" in conditions[0]
        assert "gemini" in conditions[0].lower()

    def test_prefix_applied(self):
        conditions = tool_sql_conditions("vibe", prefix="t")
        assert conditions[0].startswith("t.")

    def test_unknown_tool_raises(self):
        with pytest.raises(ValueError, match="Unknown tool"):
            tool_sql_conditions("unknown_tool")

    def test_all_valid_tools(self):
        from searchat.config.constants import VALID_TOOL_NAMES
        for tool in VALID_TOOL_NAMES:
            conditions = tool_sql_conditions(tool)
            assert isinstance(conditions, list)
            assert len(conditions) > 0
