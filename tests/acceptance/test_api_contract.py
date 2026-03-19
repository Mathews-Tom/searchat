"""Acceptance coverage for stable REST API contracts in Wave 3."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

from fastapi.testclient import TestClient

from searchat.api.app import app
from searchat.api.routers.expertise import prime_expertise
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


def test_chat_routes_preserve_stable_disabled_messages() -> None:
    client = TestClient(app)
    response = client.post(
        "/api/chat?snapshot=backup_20250101_000000",
        json={"query": "hello", "model_provider": "openai"},
    )
    assert response.status_code == 403
    assert response.json()["detail"] == "Chat is disabled in snapshot mode"

    config = SimpleNamespace(chat=SimpleNamespace(enable_rag=False, enable_citations=True))
    with patch("searchat.api.routers.chat.get_config", return_value=config):
        rag_disabled = client.post("/api/chat-rag", json={"query": "x", "model_provider": "ollama"})

    assert rag_disabled.status_code == 404
    assert rag_disabled.json()["detail"] == "RAG chat endpoint is disabled."


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


def test_saved_query_routes_preserve_stable_internal_error_message() -> None:
    client = TestClient(app)

    class BoomService:
        def list_queries(self):
            raise RuntimeError("boom")

    with patch("searchat.api.routers.queries.deps.get_saved_queries_service", return_value=BoomService()):
        response = client.get("/api/queries")

    assert response.status_code == 500
    assert response.json()["detail"] == "Internal server error"


def test_bookmark_creation_preserves_stable_not_found_message() -> None:
    client = TestClient(app)
    bookmark_dataset = SimpleNamespace(
        snapshot_name=None,
        store=Mock(get_conversation_meta=Mock(return_value=None)),
        search_dir="/tmp/searchat",
    )

    with patch("searchat.api.routers.bookmarks.deps.get_bookmarks_service") as get_bookmarks_service:
        get_bookmarks_service.return_value.add_bookmark.return_value = None
        with patch("searchat.api.routers.bookmarks.get_dataset_store", return_value=bookmark_dataset):
            response = client.post(
                "/api/bookmarks",
                json={"conversation_id": "conv-404", "notes": "important"},
            )

    assert response.status_code == 404
    assert response.json()["detail"] == "Conversation not found: conv-404"


def test_bookmark_mutation_routes_preserve_stable_success_messages() -> None:
    client = TestClient(app)
    bookmarks_service = Mock()
    bookmarks_service.remove_bookmark.return_value = True
    bookmarks_service.update_notes.return_value = True

    with patch("searchat.api.routers.bookmarks.deps.get_bookmarks_service", return_value=bookmarks_service):
        remove_response = client.delete("/api/bookmarks/conv-123")
        notes_response = client.patch(
            "/api/bookmarks/conv-123/notes",
            json={"notes": "updated"},
        )

    assert remove_response.status_code == 200
    assert remove_response.json() == {
        "success": True,
        "message": "Bookmark removed for conversation conv-123",
    }
    assert notes_response.status_code == 200
    assert notes_response.json() == {
        "success": True,
        "message": "Notes updated successfully",
    }


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


def test_dashboard_routes_preserve_stable_internal_error_message() -> None:
    client = TestClient(app)
    config = SimpleNamespace(dashboards=SimpleNamespace(enabled=True))

    class BoomService:
        def list_dashboards(self) -> list[dict]:
            raise RuntimeError("boom")

    with patch("searchat.api.routers.dashboards.deps.get_config", return_value=config):
        with patch("searchat.api.routers.dashboards.deps.get_dashboards_service", return_value=BoomService()):
            response = client.get("/api/dashboards")

    assert response.status_code == 500
    assert response.json()["detail"] == "Internal server error"


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


def test_backup_routes_preserve_stable_contracts() -> None:
    client = TestClient(app)
    backup_manager = Mock()
    backup_manager.backup_dir = "/backups"

    metadata = Mock()
    metadata.backup_path.name = "backup_20250120_100000"
    metadata.to_dict.return_value = {
        "backup_path": "/backups/backup_20250120_100000",
        "timestamp": "20250120_100000",
        "file_count": 5,
        "total_size_mb": 10.5,
    }
    backup_manager.create_backup.return_value = metadata
    backup_manager.list_backups.return_value = [metadata]
    backup_manager.get_backup_summary.return_value = {
        "name": "backup_20250120_100000",
        "backup_mode": "full",
        "encrypted": False,
        "parent_name": None,
        "chain_length": 1,
        "snapshot_browsable": True,
        "has_manifest": True,
        "valid": True,
        "errors": [],
    }
    backup_manager.validate_backup_artifact.return_value = {
        "backup_name": "backup_20250120_100000",
        "valid": True,
        "errors": [],
    }
    backup_manager.inspect_backup_chain.return_value = {
        "backup_name": "backup_20250120_100000",
        "chain": ["backup_20250120_100000"],
        "chain_length": 1,
        "valid": True,
        "errors": [],
    }

    with patch("searchat.api.routers.backup.get_backup_manager", return_value=backup_manager):
        create_response = client.post("/api/backup/create")
        list_response = client.get("/api/backup/list")
        validate_response = client.get("/api/backup/validate/backup_20250120_100000")
        chain_response = client.get("/api/backup/chain/backup_20250120_100000")

    assert create_response.status_code == 200
    assert list(create_response.json()) == ["success", "backup", "message"]
    assert list_response.status_code == 200
    assert list(list_response.json()) == ["backups", "total", "backup_directory"]
    assert validate_response.status_code == 200
    assert list(validate_response.json()) == ["backup_name", "valid", "errors"]
    assert chain_response.status_code == 200
    assert list(chain_response.json()) == ["backup_name", "chain", "chain_length", "valid", "errors"]


def test_docs_and_agent_config_routes_preserve_stable_contracts() -> None:
    client = TestClient(app)
    docs_config = SimpleNamespace(export=SimpleNamespace(enable_tech_docs=True))
    readiness = Mock()
    readiness.snapshot.return_value = Mock(
        components={
            "metadata": "ready",
            "faiss": "ready",
            "embedder": "ready",
            "embedded_model": "ready",
        },
        watcher="disabled",
        errors={},
        warmup_started_at=None,
    )

    retrieval_service = Mock()
    retrieval_service.search.return_value = SearchResults(
        results=[
            SearchResult(
                conversation_id="conv-1",
                project_id="p",
                title="T",
                created_at=datetime.now(),
                updated_at=datetime.now(),
                message_count=3,
                file_path="/home/user/.claude/projects/p/conv.jsonl",
                score=0.9,
                snippet="snippet",
                message_start_index=0,
                message_end_index=1,
            )
        ],
        total_count=1,
        search_time_ms=1.0,
        mode_used="hybrid",
    )
    patterns = [
        SimpleNamespace(
            name="Test-Driven Development",
            description="User consistently writes tests before implementation",
            evidence=[],
        )
    ]

    with patch("searchat.api.routers.docs.deps.get_config", return_value=docs_config):
        with patch(
            "searchat.api.routers.docs.get_dataset_semantic_retrieval",
            return_value=(None, retrieval_service),
        ):
            docs_response = client.post(
                "/api/docs/summary",
                json={"title": "My Doc", "sections": [{"name": "S", "query": "q"}]},
            )

    ready_pattern_retrieval = Mock()
    ready_pattern_retrieval.describe_capabilities.return_value = SimpleNamespace(
        semantic_available=True,
        reranking_available=True,
        semantic_reason=None,
        reranking_reason=None,
    )

    with patch("searchat.api.routers.docs.deps.get_config", return_value=docs_config):
        with patch("searchat.api.readiness.get_readiness", return_value=readiness):
            with patch("searchat.api.routers.docs.extract_patterns", return_value=patterns):
                with patch(
                    "searchat.api.routers.docs.deps.get_search_engine",
                    return_value=ready_pattern_retrieval,
                ):
                    agent_response = client.post(
                        "/api/export/agent-config",
                        json={"format": "claude.md", "model_provider": "ollama"},
                    )

    assert docs_response.status_code == 200
    assert list(docs_response.json()) == [
        "title",
        "format",
        "generated_at",
        "content",
        "citation_count",
        "citations",
    ]
    assert agent_response.status_code == 200
    assert list(agent_response.json()) == ["format", "content", "pattern_count", "project_filter"]


def test_admin_and_indexing_routes_preserve_stable_contracts() -> None:
    client = TestClient(app)
    watcher = Mock()
    watcher.is_running = True
    watcher.get_watched_directories.return_value = ["/tmp/watch"]
    watcher_stats = {"indexed_count": 5, "last_update": "2026-03-16T00:00:00+00:00"}

    with patch("searchat.api.routers.admin.get_watcher", return_value=watcher):
        with patch("searchat.api.routers.admin.api_state.watcher_stats", watcher_stats):
            watcher_response = client.get("/api/watcher/status")

    config = Mock()
    indexer = Mock()
    indexer.get_indexed_file_paths.return_value = set()
    indexer.index_append_only.return_value = SimpleNamespace(
        new_conversations=1,
        skipped_conversations=0,
        empty_conversations=0,
    )

    connector = SimpleNamespace(name="claude", discover_files=lambda _config: ["/tmp/conv1.jsonl"])
    indexing_state = {
        "in_progress": False,
        "operation": None,
        "started_at": None,
        "files_total": 0,
        "files_processed": 0,
    }

    with patch("searchat.api.routers.indexing.get_config", return_value=config):
        with patch("searchat.api.routers.indexing.get_indexer", return_value=indexer):
            with patch("searchat.api.routers.indexing.get_connectors", return_value=[connector]):
                with patch("searchat.api.routers.indexing.invalidate_search_index"):
                    with patch("searchat.api.routers.indexing.api_state.indexing_state", indexing_state):
                        index_response = client.post("/api/index_missing")

    assert watcher_response.status_code == 200
    assert list(watcher_response.json()) == [
        "running",
        "watched_directories",
        "indexed_since_start",
        "last_update",
    ]
    assert index_response.status_code == 200
    assert list(index_response.json()) == [
        "success",
        "new_conversations",
        "failed_conversations",
        "empty_conversations",
        "total_files",
        "already_indexed",
        "message",
        "time_seconds",
    ]


def test_resume_and_export_routes_preserve_stable_contracts() -> None:
    client = TestClient(app)
    store = Mock()
    store.get_conversation_meta.return_value = {
        "conversation_id": "conv-1",
        "file_path": "/tmp/conv-1.jsonl",
    }
    platform_manager = Mock()
    platform_manager.platform = "darwin"
    platform_manager.normalize_path.return_value = "/tmp/project"

    with patch("searchat.api.routers.conversations.deps.get_duckdb_store", return_value=store):
        with patch("searchat.api.routers.conversations.get_platform_manager", return_value=platform_manager):
            with patch(
                "searchat.api.routers.conversations.read_file_async",
                return_value='{"type":"user","cwd":"/tmp/project","message":{"content":"hi"}}\n',
            ):
                resume_response = client.post("/api/resume", json={"conversation_id": "conv-1"})

    assert resume_response.status_code == 200
    assert list(resume_response.json()) == ["success", "tool", "cwd", "command", "platform"]


def test_delete_conversations_route_preserves_stable_contract() -> None:
    client = TestClient(app)
    indexer = Mock()
    indexer.delete_conversations.return_value = {
        "deleted": 2,
        "removed_vectors": 5,
        "source_files_deleted": 1,
    }

    with patch("searchat.api.routers.conversations.deps.get_indexer", return_value=indexer):
        with patch("searchat.api.routers.conversations.invalidate_search_index"):
            response = client.request(
                "DELETE",
                "/api/conversations/delete",
                json={"conversation_ids": ["conv-1", "conv-2"], "delete_source_files": True},
            )

    assert response.status_code == 200
    assert list(response.json()) == ["deleted", "removed_vectors", "source_files_deleted"]


def test_all_conversations_route_preserves_stable_contract() -> None:
    client = TestClient(app)
    store = Mock()
    now = datetime.now()
    row = {
        "conversation_id": "conv-1",
        "project_id": "project-a",
        "title": "Contract listing",
        "created_at": now,
        "updated_at": now,
        "message_count": 3,
        "file_path": "/home/user/.claude/project-a/conv-1.jsonl",
        "full_text": "Conversation listing contract.",
    }
    store.count_conversations.return_value = 1
    store.list_conversations.return_value = [row]
    dataset = SimpleNamespace(store=store)

    with patch("searchat.api.routers.conversations.get_dataset_store", return_value=dataset):
        response = client.get("/api/conversations/all")

    assert response.status_code == 200
    assert list(response.json()) == ["results", "total", "search_time_ms"]

    with patch("searchat.api.routers.conversations.get_conversation", return_value=SimpleNamespace()):
        export_response = client.get("/api/conversation/conv-1/export?format=xml")
    assert export_response.status_code == 400
    assert export_response.json()["detail"] == "Invalid format. Use: json, markdown, text, ipynb, or pdf"


def test_expertise_and_knowledge_graph_delete_routes_preserve_stable_contract() -> None:
    client = TestClient(app)

    expertise_store = Mock()
    expertise_store.get.return_value = SimpleNamespace(id="rec-1")
    with patch("searchat.api.routers.expertise.get_expertise_store", return_value=expertise_store):
        expertise_response = client.delete("/api/expertise/rec-1")

    kg_store = Mock()
    kg_store.get_edge.return_value = SimpleNamespace(id="edge-1")
    with patch("searchat.api.routers.knowledge_graph.get_knowledge_graph_store", return_value=kg_store):
        with patch("searchat.api.routers.knowledge_graph.get_expertise_store", return_value=Mock()):
            with patch(
                "searchat.api.routers.knowledge_graph.get_config",
                return_value=SimpleNamespace(
                    knowledge_graph=SimpleNamespace(enabled=True),
                    expertise=SimpleNamespace(enabled=True),
                ),
            ):
                kg_response = client.delete("/api/knowledge-graph/edges/edge-1")

    assert expertise_response.status_code == 200
    assert list(expertise_response.json()) == ["status", "id"]
    assert kg_response.status_code == 200
    assert list(kg_response.json()) == ["status", "id"]


def test_knowledge_graph_routes_preserve_stable_validation_and_not_found_messages() -> None:
    client = TestClient(app)

    kg_store = Mock()
    kg_store.get_edge.return_value = None
    expertise_store = Mock()
    expertise_store.get.side_effect = lambda record_id: (
        SimpleNamespace(id=record_id) if record_id in {"rec-a", "rec-b"} else None
    )

    with patch("searchat.api.routers.knowledge_graph.get_knowledge_graph_store", return_value=kg_store):
        with patch("searchat.api.routers.knowledge_graph.get_expertise_store", return_value=expertise_store):
            with patch(
                "searchat.api.routers.knowledge_graph.get_config",
                return_value=SimpleNamespace(
                    knowledge_graph=SimpleNamespace(enabled=True),
                    expertise=SimpleNamespace(enabled=True),
                ),
            ):
                invalid_edge_type_response = client.post(
                    "/api/knowledge-graph/edges",
                    json={
                        "source_id": "rec-a",
                        "target_id": "rec-b",
                        "edge_type": "bad_type",
                    },
                )
                missing_edge_response = client.post(
                    "/api/knowledge-graph/resolve",
                    json={"edge_id": "edge-404", "strategy": "dismiss", "params": {"reason": "x"}},
                )
                missing_record_response = client.get("/api/knowledge-graph/lineage/rec-404")

    assert invalid_edge_type_response.status_code == 422
    assert invalid_edge_type_response.json()["detail"].startswith(
        "Invalid edge_type 'bad_type'. Must be one of:"
    )
    assert missing_edge_response.status_code == 404
    assert missing_edge_response.json()["detail"] == "Edge not found: edge-404"
    assert missing_record_response.status_code == 404
    assert missing_record_response.json()["detail"] == "Record not found: rec-404"


def test_expertise_routes_preserve_stable_validation_and_not_found_messages() -> None:
    client = TestClient(app)

    expertise_store = Mock()
    expertise_store.get.return_value = None
    expertise_store.list_domains.return_value = []

    with patch("searchat.api.routers.expertise.get_expertise_store", return_value=expertise_store):
        invalid_type_response = client.post(
            "/api/expertise",
            json={"type": "bad", "domain": "coding", "content": "x"},
        )
        missing_record_response = client.get("/api/expertise/rec-404")
        missing_domain_response = client.patch(
            "/api/expertise/domains/missing",
            json={"description": "updated"},
        )

    assert invalid_type_response.status_code == 422
    assert (
        invalid_type_response.json()["detail"]
        == "Invalid type 'bad'. Must be one of: convention, pattern, failure, decision, boundary, insight"
    )
    assert missing_record_response.status_code == 404
    assert missing_record_response.json()["detail"] == "Record not found: rec-404"
    assert missing_domain_response.status_code == 404
    assert missing_domain_response.json()["detail"] == "Domain not found: missing"


def test_conversation_detail_code_and_diff_routes_preserve_stable_contracts() -> None:
    client = TestClient(app)

    store = Mock()
    store.get_conversation_meta.return_value = None

    dataset = SimpleNamespace(store=store, snapshot_name=None)

    with patch("searchat.api.routers.conversations.get_dataset_store", return_value=dataset):
        detail_response = client.get("/api/conversation/missing")

    assert detail_response.status_code == 404
    assert detail_response.json()["detail"] == "Conversation not found in index"

    with patch(
        "searchat.api.routers.conversations.get_conversation",
        return_value=SimpleNamespace(
            title="Code sample",
            messages=[
                SimpleNamespace(
                    role="assistant",
                    content="```python\nprint('hi')\n```",
                    timestamp="2026-03-16T00:00:00Z",
                )
            ],
        ),
    ):
        code_response = client.get("/api/conversation/conv-1/code")

    assert code_response.status_code == 200
    assert list(code_response.json()) == ["conversation_id", "title", "total_blocks", "code_blocks"]

    with patch(
        "searchat.api.routers.conversations.get_conversation",
        side_effect=[
            SimpleNamespace(messages=[SimpleNamespace(role="user", content="a", timestamp="")]),
            SimpleNamespace(messages=[SimpleNamespace(role="user", content="b", timestamp="")]),
        ],
    ):
        diff_response = client.get("/api/conversation/conv-1/diff?target_id=conv-2")

    assert diff_response.status_code == 200
    assert list(diff_response.json()) == [
        "source_conversation_id",
        "target_conversation_id",
        "summary",
        "added",
        "removed",
        "unchanged",
    ]


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

    store.get_conversation_meta.return_value = None

    with patch(
        "searchat.api.routers.conversations.get_dataset_semantic_retrieval",
        return_value=(dataset, search_engine),
    ):
        response = client.get("/api/conversation/conv-404/similar")

    assert response.status_code == 404
    assert response.json()["detail"] == "Conversation not found: conv-404"


def test_search_auxiliary_routes_preserve_stable_contracts() -> None:
    client = TestClient(app)

    conn = Mock()
    conn.execute.return_value.fetchall.return_value = [("Python testing guide",), ("Pytest fixtures",)]
    store = Mock()
    store._connect.return_value = conn

    with patch("searchat.api.routers.search.deps.get_duckdb_store", return_value=store):
        suggestions_response = client.get("/api/search/suggestions?q=py")

    assert suggestions_response.status_code == 200
    assert list(suggestions_response.json()) == ["query", "suggestions"]

    code_conn = Mock()
    code_conn.execute.return_value.fetchall.return_value = [("ignored",)]
    code_store = Mock()
    code_store._connect.return_value = code_conn
    dataset = SimpleNamespace(search_dir=Path("/tmp/searchat"), snapshot_name=None, store=code_store)

    with patch("searchat.api.routers.search.get_dataset_store", return_value=dataset):
        with patch("pathlib.Path.exists", return_value=True):
            with patch("pathlib.Path.glob", return_value=[dataset.search_dir / "data" / "code" / "blocks.parquet"]):
                with patch(
                    "searchat.api.routers.search.rows_to_code_results",
                    return_value=(1, [{"conversation_id": "conv-1", "language": "python"}]),
                ):
                    code_response = client.get("/api/search/code?q=print")

    assert code_response.status_code == 200
    assert list(code_response.json()) == ["results", "total", "limit", "offset", "has_more"]


def test_code_routes_preserve_stable_error_messages() -> None:
    client = TestClient(app)

    with patch.dict("sys.modules", {"pygments": None, "pygments.formatters": None, "pygments.lexers": None}):
        highlight_response = client.post(
            "/api/code/highlight",
            json={"blocks": [{"code": "x", "language": None, "language_source": "detected"}]},
        )

    search_dir = Path("/tmp/nonexistent-code-searchat")
    store = Mock()
    store._connect.return_value = Mock()
    dataset = SimpleNamespace(search_dir=search_dir, snapshot_name=None, store=store)

    with patch("searchat.api.routers.code.get_dataset_store", return_value=dataset):
        symbols_response = client.get("/api/conversation/conv-1/code-symbols")

    with patch("searchat.api.routers.search.get_dataset_store", return_value=dataset):
        code_search_response = client.get("/api/search/code?q=print")

    assert highlight_response.status_code == 500
    assert highlight_response.json()["detail"] == "Pygments is required for code highlighting"
    assert symbols_response.status_code == 503
    assert (
        symbols_response.json()["detail"]
        == "Code index not found. Rebuild the index to enable code symbol endpoints."
    )
    assert code_search_response.status_code == 503
    assert (
        code_search_response.json()["detail"]
        == "Code index not found. Rebuild the index to enable /api/search/code."
    )


def test_expertise_prime_content_formats_preserve_stable_contract() -> None:
    record = SimpleNamespace(
        type="convention",
        domain="coding",
        content="use snake_case",
        project=None,
        severity=None,
        tags=[],
        name=None,
        example=None,
        rationale=None,
        alternatives_considered=None,
        resolution=None,
        source_conversation_id=None,
        source_agent=None,
        confidence=1.0,
        validation_count=0,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
        last_validated=datetime.now(timezone.utc),
        is_active=True,
        id="exp-1",
    )
    store = Mock()
    store.query.return_value = [record]
    config = SimpleNamespace(expertise=SimpleNamespace(default_prime_tokens=4000))

    with patch("searchat.api.routers.expertise.get_expertise_store", return_value=store):
        with patch("searchat.api.routers.expertise.get_config", return_value=config):
            markdown_response = prime_expertise(project=None, domain=None, max_tokens=None, format="markdown")
            prompt_response = prime_expertise(project=None, domain=None, max_tokens=None, format="prompt")

    assert list(markdown_response) == ["content"]
    assert list(prompt_response) == ["content"]
