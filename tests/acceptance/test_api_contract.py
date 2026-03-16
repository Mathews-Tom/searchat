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


def test_status_route_preserves_control_plane_contract() -> None:
    retrieval_service = Mock()
    retrieval_service.describe_capabilities.return_value = SimpleNamespace(
        semantic_available=True,
        reranking_available=False,
        semantic_reason=None,
        reranking_reason="Reranking disabled",
    )
    with patch("searchat.api.dependencies._search_engine", retrieval_service):
        client = TestClient(app)
        response = client.get("/api/status")

    assert response.status_code == 200
    payload = response.json()
    assert list(payload) == [
        "server_started_at",
        "warmup_started_at",
        "components",
        "watcher",
        "errors",
        "retrieval",
    ]
    assert payload["retrieval"] == {
        "semantic_available": True,
        "reranking_available": False,
        "semantic_reason": None,
        "reranking_reason": "Reranking disabled",
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


def test_saved_state_routes_preserve_stable_contracts() -> None:
    client = TestClient(app)

    bookmark = {
        "conversation_id": "conv-123",
        "added_at": "2026-03-16T00:00:00+00:00",
        "notes": "important",
    }
    store = Mock()
    store.get_conversation_meta.return_value = {
        "conversation_id": "conv-123",
        "title": "Stable Bookmark",
        "project_id": "project-a",
        "message_count": 5,
        "created_at": datetime(2026, 3, 16),
        "updated_at": datetime(2026, 3, 17),
    }
    bookmark_dataset = SimpleNamespace(snapshot_name=None, store=store, search_dir="/tmp/searchat")
    query = {
        "id": "q-123",
        "name": "Release Checks",
        "description": "smoke",
        "query": "deployment",
        "filters": {},
        "mode": "hybrid",
        "created_at": "2026-03-16T00:00:00+00:00",
        "last_used": None,
        "use_count": 0,
    }
    queries_service = Mock()
    queries_service.list_queries.return_value = [query]

    with patch("searchat.api.routers.bookmarks.deps.get_bookmarks_service") as get_bookmarks_service:
        get_bookmarks_service.return_value.list_bookmarks.return_value = [bookmark]
        with patch("searchat.api.routers.bookmarks.get_dataset_store", return_value=bookmark_dataset):
            bookmarks_response = client.get("/api/bookmarks")

    with patch("searchat.api.routers.queries.deps.get_saved_queries_service", return_value=queries_service):
        queries_response = client.get("/api/queries")

    assert bookmarks_response.status_code == 200
    assert list(bookmarks_response.json()) == ["total", "bookmarks"]
    assert list(bookmarks_response.json()["bookmarks"][0]) == [
        "conversation_id",
        "added_at",
        "notes",
        "title",
        "project_id",
        "message_count",
        "created_at",
        "updated_at",
    ]

    assert queries_response.status_code == 200
    assert list(queries_response.json()) == ["total", "queries"]
    assert list(queries_response.json()["queries"][0]) == [
        "id",
        "name",
        "description",
        "query",
        "filters",
        "mode",
        "created_at",
        "last_used",
        "use_count",
    ]


def test_dashboard_routes_preserve_stable_contracts() -> None:
    client = TestClient(app)
    config = SimpleNamespace(dashboards=SimpleNamespace(enabled=True))
    dashboard = {
        "id": "d-123",
        "name": "Daily Ops",
        "description": None,
        "queries": ["q-1"],
        "layout": {"widgets": [{"id": "w-1", "query_id": "q-1"}]},
        "refresh_interval": None,
        "created_at": "2026-03-16T00:00:00+00:00",
        "updated_at": "2026-03-16T00:00:00+00:00",
    }
    dashboards_service = Mock()
    dashboards_service.list_dashboards.return_value = [dashboard]

    with patch("searchat.api.routers.dashboards.deps.get_config", return_value=config):
        with patch("searchat.api.routers.dashboards.deps.get_dashboards_service", return_value=dashboards_service):
            list_response = client.get("/api/dashboards")
            dashboards_service.get_dashboard.return_value = dashboard
            get_response = client.get("/api/dashboards/d-123")

    assert list_response.status_code == 200
    assert list(list_response.json()) == ["total", "dashboards"]
    assert list(list_response.json()["dashboards"][0]) == [
        "id",
        "name",
        "description",
        "queries",
        "layout",
        "refresh_interval",
        "created_at",
        "updated_at",
    ]

    assert get_response.status_code == 200
    assert list(get_response.json()) == ["dashboard"]


def test_analytics_routes_preserve_stable_contracts() -> None:
    client = TestClient(app)
    analytics = Mock()
    analytics.get_stats_summary.return_value = {
        "total_searches": 100,
        "unique_queries": 50,
        "avg_results": 12.5,
        "avg_time_ms": 150.0,
        "mode_distribution": {"hybrid": 60},
    }
    analytics.get_top_queries.return_value = [{"query": "python", "search_count": 3}]
    analytics.get_dead_end_queries.return_value = [{"query": "rare", "search_count": 1}]
    analytics.get_trends.return_value = [{"day": "2026-01-01", "searches": 3}]
    analytics.get_agent_comparison.return_value = [{"tool_filter": "all", "searches": 10}]
    analytics.get_topic_clusters.return_value = [{"cluster_id": 0, "searches": 10}]
    config = SimpleNamespace(analytics=SimpleNamespace(enabled=True, retention_days=14))

    with patch("searchat.api.routers.stats.deps.get_analytics_service", return_value=analytics):
        with patch("searchat.api.routers.stats.deps.get_config", return_value=config):
            summary_response = client.get("/api/stats/analytics/summary")
            top_queries_response = client.get("/api/stats/analytics/top-queries")
            trends_response = client.get("/api/stats/analytics/trends")
            agent_response = client.get("/api/stats/analytics/agent-comparison")
            topics_response = client.get("/api/stats/analytics/topics")
            config_response = client.get("/api/stats/analytics/config")

    assert summary_response.status_code == 200
    assert list(summary_response.json()) == [
        "total_searches",
        "unique_queries",
        "avg_results",
        "avg_time_ms",
        "mode_distribution",
    ]
    assert top_queries_response.status_code == 200
    assert list(top_queries_response.json()) == ["queries", "days"]
    assert trends_response.status_code == 200
    assert list(trends_response.json()) == ["days", "points"]
    assert agent_response.status_code == 200
    assert list(agent_response.json()) == ["days", "tools"]
    assert topics_response.status_code == 200
    assert list(topics_response.json()) == ["days", "clusters"]
    assert config_response.status_code == 200
    assert list(config_response.json()) == ["enabled", "retention_days"]


def test_search_and_similarity_routes_preserve_stable_error_messages() -> None:
    client = TestClient(app)
    dataset = SimpleNamespace(
        search_dir="/tmp/searchat",
        snapshot_name=None,
        retrieval_service=Mock(),
    )

    response = client.get("/api/search?q=test&mode=invalid")
    assert response.status_code == 400
    assert response.json()["detail"] == "Invalid search mode"

    with patch("searchat.api.routers.search.get_dataset_retrieval", return_value=dataset):
        response = client.get("/api/search?q=test&tool=bad")
    assert response.status_code == 400
    assert response.json()["detail"] == "Invalid tool filter"

    with patch("searchat.api.routers.search.get_dataset_retrieval", return_value=dataset):
        response = client.get("/api/search?q=python&highlight=true")
    assert response.status_code == 400
    assert response.json()["detail"] == "Highlight provider is required"

    with patch("searchat.api.routers.search.get_dataset_retrieval", return_value=dataset):
        response = client.get("/api/search?q=python&highlight=true&highlight_provider=bad")
    assert response.status_code == 400
    assert response.json()["detail"] == "Invalid highlight provider"

    store = Mock()
    store.get_conversation_meta.return_value = {
        "conversation_id": "conv-123",
        "title": "Conversation",
        "project_id": "project-a",
    }
    conn = Mock()
    conn.execute.return_value.fetchone.return_value = None
    store._connect.return_value = conn
    search_engine = Mock()
    search_engine.metadata_path = "/tmp/meta.parquet"
    dataset = SimpleNamespace(store=store)

    with patch(
        "searchat.api.routers.conversations.get_dataset_semantic_retrieval",
        return_value=(dataset, search_engine),
    ):
        response = client.get("/api/conversation/conv-123/similar")

    assert response.status_code == 404
    assert response.json()["detail"] == "No embeddings found for this conversation"
