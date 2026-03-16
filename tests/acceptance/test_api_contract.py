"""Acceptance coverage for stable REST API contracts in Wave 3."""
from __future__ import annotations

from datetime import datetime, timedelta
from types import SimpleNamespace
from unittest.mock import Mock, patch

from fastapi.testclient import TestClient

from searchat.api.app import app
from searchat.models import SearchResult, SearchResults
from searchat.services.llm_service import LLMServiceError


def test_status_features_exposes_retrieval_capability_snapshot() -> None:
    retrieval_service = Mock()
    retrieval_service.describe_capabilities.return_value = SimpleNamespace(
        semantic_available=False,
        reranking_available=True,
        semantic_reason="Embedding model unavailable: all-MiniLM-L6-v2",
        reranking_reason=None,
    )
    config = SimpleNamespace(
        analytics=SimpleNamespace(enabled=True),
        chat=SimpleNamespace(enable_rag=True, enable_citations=True),
        export=SimpleNamespace(enable_ipynb=False, enable_pdf=True, enable_tech_docs=False),
        dashboards=SimpleNamespace(enabled=True),
        snapshots=SimpleNamespace(enabled=True),
    )

    with patch("searchat.api.routers.status.deps.get_config", return_value=config):
        with patch("searchat.api.dependencies._search_engine", retrieval_service):
            client = TestClient(app)
            response = client.get("/api/status/features")

    assert response.status_code == 200
    payload = response.json()
    assert payload["retrieval"] == {
        "semantic_available": False,
        "reranking_available": True,
        "semantic_reason": "Embedding model unavailable: all-MiniLM-L6-v2",
        "reranking_reason": None,
    }


def test_chat_rag_generation_outage_returns_grounded_fallback_with_sources() -> None:
    readiness = Mock()
    readiness.snapshot.return_value = Mock(
        components={"metadata": "ready", "faiss": "ready", "embedder": "ready"}
    )
    now = datetime.now()
    retrieval_service = Mock()
    retrieval_service.search.return_value = SearchResults(
        results=[
            SearchResult(
                conversation_id="conv-123",
                project_id="project-a",
                title="Archival Note",
                created_at=now - timedelta(days=2),
                updated_at=now - timedelta(days=1),
                message_count=5,
                file_path="/tmp/conv-123.jsonl",
                score=0.9,
                snippet="Pinned implementation note.",
                message_start_index=1,
                message_end_index=2,
            )
        ],
        total_count=1,
        search_time_ms=4.0,
        mode_used="hybrid",
    )
    config = SimpleNamespace(
        chat=SimpleNamespace(enable_rag=True, enable_citations=True),
        llm=SimpleNamespace(
            default_provider="ollama",
            openai_model="gpt-4.1-mini",
            ollama_model="llama3",
        ),
    )

    with patch("searchat.api.readiness.get_readiness", return_value=readiness):
        with patch("searchat.api.routers.chat.get_config", return_value=config):
            with patch("searchat.api.routers.chat.get_search_engine", return_value=retrieval_service):
                with patch("searchat.services.chat_service.build_generation_service") as mock_builder:
                    mock_builder.return_value.completion.side_effect = LLMServiceError("provider down")
                    client = TestClient(app)
                    response = client.post(
                        "/api/chat-rag",
                        json={"query": "Summarize the history", "model_provider": "ollama"},
                    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["answer"].startswith("Generation is temporarily unavailable.")
    assert payload["sources"][0]["conversation_id"] == "conv-123"


def test_search_highlight_provider_failure_degrades_to_plain_search() -> None:
    now = datetime.now()
    retrieval_service = Mock()
    retrieval_service.search.return_value = SearchResults(
        results=[
            SearchResult(
                conversation_id="conv-123",
                project_id="project-a",
                title="Search Result",
                created_at=now - timedelta(days=2),
                updated_at=now - timedelta(days=1),
                message_count=3,
                file_path="/tmp/conv-123.jsonl",
                score=0.8,
                snippet="Important python snippet.",
            )
        ],
        total_count=1,
        search_time_ms=3.0,
        mode_used="hybrid",
    )
    dataset = SimpleNamespace(
        search_dir="/tmp/searchat",
        snapshot_name=None,
        retrieval_service=retrieval_service,
    )
    config = SimpleNamespace(analytics=SimpleNamespace(enabled=False))

    with patch("searchat.api.routers.search.get_dataset_retrieval", return_value=dataset):
        with patch("searchat.api.routers.search.deps.get_config", return_value=config):
            with patch(
                "searchat.api.routers.search.extract_highlight_terms",
                side_effect=LLMServiceError("provider down"),
            ):
                client = TestClient(app)
                response = client.get(
                    "/api/search?q=python&highlight=true&highlight_provider=openai"
                )

    assert response.status_code == 200
    payload = response.json()
    assert payload["highlight_terms"] is None
    assert payload["results"][0]["conversation_id"] == "conv-123"


def test_search_route_preserves_stable_result_contract() -> None:
    now = datetime.now()
    retrieval_service = Mock()
    retrieval_service.search.return_value = SearchResults(
        results=[
            SearchResult(
                conversation_id="conv-123",
                project_id="project-a",
                title="Stable Search Result",
                created_at=now - timedelta(days=2),
                updated_at=now - timedelta(days=1),
                message_count=3,
                file_path="/home/user/.claude/conv-123.jsonl",
                score=0.8,
                snippet="Contract payload coverage.",
                message_start_index=1,
                message_end_index=2,
            )
        ],
        total_count=1,
        search_time_ms=3.0,
        mode_used="hybrid",
    )
    dataset = SimpleNamespace(
        search_dir="/tmp/searchat",
        snapshot_name=None,
        retrieval_service=retrieval_service,
    )
    config = SimpleNamespace(analytics=SimpleNamespace(enabled=False))

    with patch("searchat.api.routers.search.get_dataset_retrieval", return_value=dataset):
        with patch("searchat.api.routers.search.deps.get_config", return_value=config):
            client = TestClient(app)
            response = client.get("/api/search?q=contract")

    assert response.status_code == 200
    payload = response.json()
    assert list(payload) == [
        "results",
        "total",
        "search_time_ms",
        "limit",
        "offset",
        "has_more",
        "highlight_terms",
    ]
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
        "source",
        "tool",
    ]


def test_projects_and_statistics_routes_preserve_stable_contracts() -> None:
    stats = SimpleNamespace(
        total_conversations=10,
        total_messages=100,
        avg_messages=10.0,
        total_projects=2,
        earliest_date="2025-01-01T00:00:00",
        latest_date="2025-06-01T00:00:00",
    )
    store = Mock()
    store.list_projects.return_value = ["proj-a", "proj-b"]
    store.get_statistics.return_value = stats
    dataset = SimpleNamespace(snapshot_name=None, store=store, search_dir="/tmp/searchat")

    with patch("searchat.api.routers.search.get_dataset_store", return_value=dataset):
        with patch("searchat.api.routers.search.api_state.projects_cache", None):
            client = TestClient(app)
            projects_response = client.get("/api/projects")

    with patch("searchat.api.routers.stats.get_dataset_store", return_value=dataset):
        with patch("searchat.api.routers.stats.api_state.stats_cache", None):
            client = TestClient(app)
            stats_response = client.get("/api/statistics")

    assert projects_response.status_code == 200
    assert projects_response.json() == ["proj-a", "proj-b"]

    assert stats_response.status_code == 200
    stats_payload = stats_response.json()
    assert list(stats_payload) == [
        "total_conversations",
        "total_messages",
        "avg_messages",
        "total_projects",
        "earliest_date",
        "latest_date",
    ]
