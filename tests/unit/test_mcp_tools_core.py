"""Tests for MCP tools utility functions and core tool functions."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from searchat.mcp.tools import (
    _json_default,
    _json_dumps,
    build_services,
    parse_mode,
    parse_tool,
    resolve_dataset,
)
from searchat.models import SearchMode


class TestJsonDefault:
    def test_serializes_datetime(self):
        dt = datetime(2025, 1, 15, 12, 0, 0, tzinfo=timezone.utc)
        assert _json_default(dt) == dt.isoformat()

    def test_raises_for_non_datetime(self):
        with pytest.raises(TypeError, match="not JSON serializable"):
            _json_default(object())


class TestJsonDumps:
    def test_serializes_with_datetime(self):
        dt = datetime(2025, 6, 1, tzinfo=timezone.utc)
        result = _json_dumps({"ts": dt, "name": "test"})
        parsed = json.loads(result)
        assert parsed["ts"] == dt.isoformat()
        assert parsed["name"] == "test"


class TestResolveDataset:
    def test_returns_base_dir_when_search_dir_none(self, tmp_path: Path):
        cfg = MagicMock()
        with (
            patch("searchat.mcp.tools.Config.load", return_value=cfg),
            patch("searchat.mcp.tools.PathResolver.get_shared_search_dir", return_value=tmp_path),
        ):
            result = resolve_dataset(None)
        assert result == tmp_path

    def test_returns_base_dir_when_search_dir_empty(self, tmp_path: Path):
        cfg = MagicMock()
        with (
            patch("searchat.mcp.tools.Config.load", return_value=cfg),
            patch("searchat.mcp.tools.PathResolver.get_shared_search_dir", return_value=tmp_path),
        ):
            result = resolve_dataset("  ")
        assert result == tmp_path

    def test_returns_resolved_path_when_exists(self, tmp_path: Path):
        cfg = MagicMock()
        with (
            patch("searchat.mcp.tools.Config.load", return_value=cfg),
            patch("searchat.mcp.tools.PathResolver.get_shared_search_dir", return_value=tmp_path),
        ):
            result = resolve_dataset(str(tmp_path))
        assert result == tmp_path

    def test_raises_when_path_does_not_exist(self, tmp_path: Path):
        missing = tmp_path / "nonexistent"
        cfg = MagicMock()
        with (
            patch("searchat.mcp.tools.Config.load", return_value=cfg),
            patch("searchat.mcp.tools.PathResolver.get_shared_search_dir", return_value=tmp_path),
        ):
            with pytest.raises(FileNotFoundError, match="does not exist"):
                resolve_dataset(str(missing))


class TestParseMode:
    def test_hybrid(self):
        assert parse_mode("hybrid") == SearchMode.HYBRID

    def test_semantic(self):
        assert parse_mode("SEMANTIC") == SearchMode.SEMANTIC

    def test_keyword(self):
        assert parse_mode("  keyword  ") == SearchMode.KEYWORD

    def test_invalid_raises(self):
        with pytest.raises(ValueError, match="Invalid mode"):
            parse_mode("bm25")


class TestParseTool:
    def test_none_returns_none(self):
        assert parse_tool(None) is None

    def test_empty_returns_none(self):
        assert parse_tool("") is None
        assert parse_tool("   ") is None

    def test_valid_tool_returns_lowercase(self):
        assert parse_tool("Claude") == "claude"

    def test_invalid_tool_raises(self):
        with pytest.raises(ValueError, match="Invalid tool"):
            parse_tool("nonexistent_tool_xyz")


class TestBuildServices:
    def test_creates_config_engine_store(self, tmp_path: Path):
        cfg = MagicMock()
        cfg.performance.memory_limit_mb = 256
        fake_engine = MagicMock()
        fake_store = MagicMock()

        with (
            patch("searchat.mcp.tools.Config.load", return_value=cfg),
            patch("searchat.mcp.tools.SearchEngine", return_value=fake_engine),
            patch("searchat.mcp.tools.DuckDBStore", return_value=fake_store),
        ):
            config, engine, store = build_services(tmp_path)

        assert config is cfg
        assert engine is fake_engine
        assert store is fake_store


class TestSearchConversations:
    def test_limit_validation(self):
        from searchat.mcp.tools import search_conversations

        with pytest.raises(ValueError, match="limit must be between"):
            search_conversations(query="test", limit=0)
        with pytest.raises(ValueError, match="limit must be between"):
            search_conversations(query="test", limit=200)

    def test_offset_validation(self):
        from searchat.mcp.tools import search_conversations

        with pytest.raises(ValueError, match="offset must be >= 0"):
            search_conversations(query="test", offset=-1)

    def test_returns_json_with_results(self, tmp_path: Path):
        from searchat.mcp.tools import search_conversations

        fake_result = MagicMock()
        fake_result.results = []
        fake_result.mode_used = "hybrid"
        fake_result.search_time_ms = 42.0

        cfg = MagicMock()
        fake_engine = MagicMock()
        fake_engine.search.return_value = fake_result
        fake_store = MagicMock()

        with (
            patch("searchat.mcp.tools.resolve_dataset", return_value=tmp_path),
            patch("searchat.mcp.tools.build_services", return_value=(cfg, fake_engine, fake_store)),
        ):
            result = search_conversations(query="hello")

        parsed = json.loads(result)
        assert parsed["results"] == []
        assert parsed["mode_used"] == "hybrid"


class TestGetConversation:
    def test_raises_when_not_found(self, tmp_path: Path):
        from searchat.mcp.tools import get_conversation

        fake_store = MagicMock()
        fake_store.get_conversation_record.return_value = None

        with (
            patch("searchat.mcp.tools.resolve_dataset", return_value=tmp_path),
            patch("searchat.mcp.tools.build_services", return_value=(MagicMock(), MagicMock(), fake_store)),
        ):
            with pytest.raises(ValueError, match="Conversation not found"):
                get_conversation(conversation_id="missing")

    def test_returns_json_when_found(self, tmp_path: Path):
        from searchat.mcp.tools import get_conversation

        fake_store = MagicMock()
        fake_store.get_conversation_record.return_value = {"id": "abc", "title": "Test"}

        with (
            patch("searchat.mcp.tools.resolve_dataset", return_value=tmp_path),
            patch("searchat.mcp.tools.build_services", return_value=(MagicMock(), MagicMock(), fake_store)),
        ):
            result = get_conversation(conversation_id="abc")

        parsed = json.loads(result)
        assert parsed["id"] == "abc"


class TestListProjects:
    def test_returns_json_projects(self, tmp_path: Path):
        from searchat.mcp.tools import list_projects

        fake_store = MagicMock()
        fake_store.list_projects.return_value = ["proj-a", "proj-b"]

        with (
            patch("searchat.mcp.tools.resolve_dataset", return_value=tmp_path),
            patch("searchat.mcp.tools.build_services", return_value=(MagicMock(), MagicMock(), fake_store)),
        ):
            result = list_projects()

        parsed = json.loads(result)
        assert parsed["projects"] == ["proj-a", "proj-b"]


class TestGetStatistics:
    def test_returns_json_stats(self, tmp_path: Path):
        from searchat.mcp.tools import get_statistics

        stats = SimpleNamespace(
            total_conversations=10,
            total_messages=100,
            avg_messages=10.0,
            total_projects=2,
            earliest_date="2025-01-01",
            latest_date="2025-06-01",
        )
        fake_store = MagicMock()
        fake_store.get_statistics.return_value = stats

        with (
            patch("searchat.mcp.tools.resolve_dataset", return_value=tmp_path),
            patch("searchat.mcp.tools.build_services", return_value=(MagicMock(), MagicMock(), fake_store)),
        ):
            result = get_statistics()

        parsed = json.loads(result)
        assert parsed["total_conversations"] == 10
        assert parsed["total_projects"] == 2


class TestGenerateAgentConfig:
    def test_invalid_format_raises(self):
        from searchat.mcp.tools import generate_agent_config

        with pytest.raises(ValueError, match="format must be"):
            generate_agent_config(format="invalid.txt")

    def test_invalid_provider_raises(self, tmp_path: Path):
        from searchat.mcp.tools import generate_agent_config

        cfg = MagicMock()
        cfg.llm.default_provider = "openai"

        with (
            patch("searchat.mcp.tools.resolve_dataset", return_value=tmp_path),
            patch("searchat.mcp.tools.build_services", return_value=(cfg, MagicMock(), MagicMock())),
        ):
            with pytest.raises(ValueError, match="model_provider must be"):
                generate_agent_config(model_provider="azure")

    def test_returns_json_with_content(self, tmp_path: Path):
        from searchat.mcp.tools import generate_agent_config

        cfg = MagicMock()
        cfg.llm.default_provider = "ollama"
        fake_pattern = SimpleNamespace(
            name="Test Pattern",
            description="A test",
            confidence=0.8,
            evidence=[SimpleNamespace(date="2025-01-01", snippet="example snippet")],
        )

        with (
            patch("searchat.mcp.tools.resolve_dataset", return_value=tmp_path),
            patch("searchat.mcp.tools.build_services", return_value=(cfg, MagicMock(), MagicMock())),
            patch("searchat.services.pattern_mining.extract_patterns", return_value=[fake_pattern]),
        ):
            result = generate_agent_config(format="claude.md")

        parsed = json.loads(result)
        assert parsed["format"] == "claude.md"
        assert parsed["pattern_count"] == 1
        assert "content" in parsed
