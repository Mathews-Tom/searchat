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
