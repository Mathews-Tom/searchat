"""Tests for searchat.core.filters.tool_sql_conditions."""
from __future__ import annotations

import pytest

from searchat.core.filters import tool_sql_conditions


class TestToolSqlConditions:
    """Tests for tool_sql_conditions."""

    def test_claude_returns_exclusion_conditions(self):
        conditions = tool_sql_conditions("claude")
        assert len(conditions) > 0
        assert all("NOT LIKE" in c or "NOT ILIKE" in c or "!=" in c for c in conditions)
        assert any("omp" in c for c in conditions)

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

    def test_omp_uses_file_path_condition(self):
        conditions = tool_sql_conditions("omp")
        assert len(conditions) == 1
        assert "ILIKE" in conditions[0]
        assert ".omp/agent/sessions" in conditions[0]

    def test_omp_also_matches_windows_backslash_path(self):
        # file_path is stored with native OS separators; on Windows that's
        # backslashes, which the forward-slash-only pattern would miss.
        conditions = tool_sql_conditions("omp")
        assert len(conditions) == 1
        assert ".omp\\agent\\sessions" in conditions[0]

    def test_omp_condition_prefix_applied_to_both_alternatives(self):
        conditions = tool_sql_conditions("omp", prefix="c")
        assert len(conditions) == 1
        assert conditions[0].count("c.file_path") == 2

    def test_all_valid_tools(self):
        from searchat.config.constants import VALID_TOOL_NAMES
        for tool in VALID_TOOL_NAMES:
            conditions = tool_sql_conditions(tool)
            assert isinstance(conditions, list)
            assert len(conditions) > 0


class TestOmpConditionAgainstDuckDB:
    """Executes the generated SQL against real DuckDB to prove semantics,
    not just string shape -- both POSIX and Windows-separator paths must
    match the omp condition, and a claude-style path must not.
    """

    def test_condition_matches_both_path_styles(self):
        import duckdb

        condition = tool_sql_conditions("omp")[0]
        con = duckdb.connect(":memory:")

        posix_path = "/home/user/.omp/agent/sessions/-proj/2026-01-01T00-00-00-000Z_uuid.jsonl"
        windows_path = r"C:\Users\user\.omp\agent\sessions\-proj\2026-01-01T00-00-00-000Z_uuid.jsonl"
        claude_path = r"C:\Users\user\.claude\projects\proj\conv.jsonl"

        for path, expected in ((posix_path, True), (windows_path, True), (claude_path, False)):
            row = con.execute(f"SELECT ({condition}) FROM (SELECT ? AS file_path)", [path]).fetchone()
            assert row is not None
            assert row[0] is expected, f"{path!r} expected {expected}, got {row[0]}"
