"""Acceptance coverage for MCP tool contracts in Wave 3."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from searchat.mcp.tools import ask_about_history, extract_patterns, find_similar_conversations
from searchat.models import SearchResult, SearchResults
from searchat.services.llm_service import LLMServiceError
from searchat.mcp.tools import get_statistics, list_projects, search_conversations
from searchat.services.retrieval_service import SemanticVectorHit


def test_ask_about_history_generation_outage_returns_grounded_fallback(tmp_path: Path) -> None:
    now = datetime.now(timezone.utc)
    engine = MagicMock()
    engine.search.return_value = SearchResults(
        results=[
            SearchResult(
                conversation_id="conv-123",
                project_id="project-a",
                title="Archival Context",
                created_at=now,
                updated_at=now,
                message_count=4,
                file_path="/tmp/conv-123.jsonl",
                score=0.9,
                snippet="Grounded implementation detail.",
            )
        ],
        total_count=1,
        search_time_ms=2.0,
        mode_used="hybrid",
    )
    config = SimpleNamespace(
        llm=SimpleNamespace(
            default_provider="ollama",
            openai_model="gpt-4.1-mini",
            ollama_model="llama3",
        )
    )

    with (
        patch("searchat.mcp.tools.resolve_dataset", return_value=tmp_path),
        patch("searchat.mcp.tools.build_services", return_value=(config, engine, MagicMock())),
        patch("searchat.mcp.tools.build_generation_service") as mock_builder,
    ):
        mock_builder.return_value.completion.side_effect = LLMServiceError("provider down")
        payload = json.loads(
            ask_about_history(
                question="What happened?",
                include_sources=True,
                search_dir=str(tmp_path),
            )
        )

    assert payload["answer"].startswith("Generation is temporarily unavailable.")
    assert payload["sources"][0]["conversation_id"] == "conv-123"
    assert list(payload["sources"][0]) == [
        "conversation_id",
        "project_id",
        "title",
        "score",
        "snippet",
        "message_start_index",
        "message_end_index",
        "tool",
    ]


def test_search_conversations_preserves_stable_result_contract(tmp_path: Path) -> None:
    now = datetime.now(timezone.utc)
    engine = MagicMock()
    engine.search.return_value = SearchResults(
        results=[
            SearchResult(
                conversation_id="conv-123",
                project_id="project-a",
                title="Contract result",
                created_at=now,
                updated_at=now,
                message_count=5,
                file_path="/tmp/conv-123.jsonl",
                score=0.8,
                snippet="Wave 4 contract coverage.",
                message_start_index=1,
                message_end_index=2,
            )
        ],
        total_count=1,
        search_time_ms=3.0,
        mode_used="hybrid",
    )

    with (
        patch("searchat.mcp.tools.resolve_dataset", return_value=tmp_path),
        patch("searchat.mcp.tools.build_services", return_value=(MagicMock(), engine, MagicMock())),
    ):
        payload = json.loads(search_conversations(query="contract", search_dir=str(tmp_path)))

    assert list(payload) == ["results", "total", "limit", "offset", "mode_used", "search_time_ms"]
    assert list(payload["results"][0]) == [
        "conversation_id",
        "project_id",
        "title",
        "created_at",
        "updated_at",
        "message_count",
        "file_path",
        "snippet",
        "score",
        "message_start_index",
        "message_end_index",
    ]


def test_project_and_statistics_tools_preserve_stable_top_level_contracts(tmp_path: Path) -> None:
    stats = SimpleNamespace(
        total_conversations=10,
        total_messages=100,
        avg_messages=10.0,
        total_projects=2,
        earliest_date="2025-01-01",
        latest_date="2025-06-01",
    )
    store = MagicMock()
    store.list_projects.return_value = ["proj-a", "proj-b"]
    store.get_statistics.return_value = stats

    with (
        patch("searchat.mcp.tools.resolve_dataset", return_value=tmp_path),
        patch("searchat.mcp.tools.build_services", return_value=(MagicMock(), MagicMock(), store)),
    ):
        projects_payload = json.loads(list_projects(search_dir=str(tmp_path)))
        stats_payload = json.loads(get_statistics(search_dir=str(tmp_path)))

    assert list(projects_payload) == ["projects"]
    assert projects_payload["projects"] == ["proj-a", "proj-b"]
    assert list(stats_payload) == [
        "total_conversations",
        "total_messages",
        "avg_messages",
        "total_projects",
        "earliest_date",
        "latest_date",
    ]


def test_find_similar_conversations_surfaces_semantic_capability_failure(tmp_path: Path) -> None:
    engine = MagicMock()
    engine.metadata_path = tmp_path / "metadata.parquet"
    engine.find_similar_vector_hits.side_effect = RuntimeError("FAISS index not available")
    store = MagicMock()
    store.get_conversation_meta.return_value = {
        "conversation_id": "conv-123",
        "title": "Conversation",
    }
    conn = MagicMock()
    conn.execute.return_value.fetchone.return_value = ("representative chunk",)
    store._connect.return_value = conn

    with (
        patch("searchat.mcp.tools.resolve_dataset", return_value=tmp_path),
        patch("searchat.mcp.tools.build_services", return_value=(MagicMock(), engine, store)),
    ):
        with pytest.raises(RuntimeError, match="FAISS index not available"):
            find_similar_conversations(conversation_id="conv-123", search_dir=str(tmp_path))


def test_extract_patterns_generation_outage_returns_fallback_payload(tmp_path: Path) -> None:
    config = SimpleNamespace(
        llm=SimpleNamespace(
            default_provider="ollama",
            openai_model="gpt-4.1-mini",
            ollama_model="llama3",
        )
    )
    engine = MagicMock()

    fake_pattern = SimpleNamespace(
        name="testing conventions",
        description="Pattern cluster related to: testing conventions",
        confidence=0.3,
        evidence=[SimpleNamespace(conversation_id="conv-123", date="2026-01-15", snippet="Start from failing tests.")],
    )

    with (
        patch("searchat.mcp.tools.resolve_dataset", return_value=tmp_path),
        patch("searchat.mcp.tools.build_services", return_value=(config, engine, MagicMock())),
        patch("searchat.services.pattern_mining.extract_patterns", return_value=[fake_pattern]),
    ):
        payload = json.loads(
            extract_patterns(topic="testing", max_patterns=1, search_dir=str(tmp_path))
        )

    assert payload["total"] == 1
    assert payload["patterns"][0]["name"] == "testing conventions"
    assert payload["patterns"][0]["confidence"] == pytest.approx(0.3)


def test_find_similar_conversations_preserves_stable_similarity_contract(tmp_path: Path) -> None:
    engine = MagicMock()
    engine.metadata_path = tmp_path / "metadata.parquet"
    engine.conversations_glob = str(tmp_path / "*.parquet")
    engine.find_similar_vector_hits.return_value = [
        SemanticVectorHit(vector_id=100, distance=0.25),
    ]
    store = MagicMock()
    store.get_conversation_meta.return_value = {
        "conversation_id": "conv-123",
        "title": "Original conversation",
    }
    conn = MagicMock()
    conn.execute.return_value.fetchone.return_value = ("representative chunk",)
    conn.execute.return_value.fetchall.return_value = [
        (
            "conv-456",
            "project-a",
            "Similar conversation",
            "2026-01-20T10:00:00+00:00",
            "2026-01-21T10:00:00+00:00",
            4,
            "/tmp/conv-456.jsonl",
            0.25,
        )
    ]
    store._connect.return_value = conn

    with (
        patch("searchat.mcp.tools.resolve_dataset", return_value=tmp_path),
        patch("searchat.mcp.tools.build_services", return_value=(MagicMock(), engine, store)),
    ):
        payload = json.loads(
            find_similar_conversations(conversation_id="conv-123", search_dir=str(tmp_path))
        )

    assert list(payload) == ["conversation_id", "title", "similar_count", "similar_conversations"]
    assert payload["similar_count"] == 1
    assert list(payload["similar_conversations"][0]) == [
        "conversation_id",
        "project_id",
        "title",
        "created_at",
        "updated_at",
        "message_count",
        "similarity_score",
        "tool",
    ]


def test_find_similar_conversations_empty_results_preserves_full_envelope(tmp_path: Path) -> None:
    engine = MagicMock()
    engine.metadata_path = tmp_path / "metadata.parquet"
    engine.conversations_glob = str(tmp_path / "*.parquet")
    engine.find_similar_vector_hits.return_value = []
    store = MagicMock()
    store.get_conversation_meta.return_value = {
        "conversation_id": "conv-123",
        "title": "Original conversation",
    }
    conn = MagicMock()
    conn.execute.return_value.fetchone.return_value = ("representative chunk",)
    store._connect.return_value = conn

    with (
        patch("searchat.mcp.tools.resolve_dataset", return_value=tmp_path),
        patch("searchat.mcp.tools.build_services", return_value=(MagicMock(), engine, store)),
    ):
        payload = json.loads(
            find_similar_conversations(conversation_id="conv-123", search_dir=str(tmp_path))
        )

    assert payload == {
        "conversation_id": "conv-123",
        "title": "Original conversation",
        "similar_count": 0,
        "similar_conversations": [],
    }


def test_mcp_tools_preserve_stable_validation_and_not_found_messages(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="^Invalid mode; expected: hybrid, semantic, keyword$"):
        search_conversations(query="contract", mode="invalid", search_dir=str(tmp_path))

    with pytest.raises(ValueError, match="^Invalid tool; expected one of: "):
        search_conversations(query="contract", tool="invalid", search_dir=str(tmp_path))

    with pytest.raises(ValueError, match="^limit must be between 1 and 100$"):
        search_conversations(query="contract", limit=0, search_dir=str(tmp_path))

    with pytest.raises(ValueError, match="^offset must be >= 0$"):
        search_conversations(query="contract", offset=-1, search_dir=str(tmp_path))

    store = MagicMock()
    store.get_conversation_meta.return_value = None
    with (
        patch("searchat.mcp.tools.resolve_dataset", return_value=tmp_path),
        patch("searchat.mcp.tools.build_services", return_value=(MagicMock(), MagicMock(), store)),
    ):
        with pytest.raises(ValueError, match=r"^Conversation not found: conv-404$"):
            find_similar_conversations(conversation_id="conv-404", search_dir=str(tmp_path))
