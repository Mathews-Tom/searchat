from __future__ import annotations

import time
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import duckdb
import pytest

from searchat.config import Config
from searchat.models import SearchResult, SearchResults
from searchat.services.analytics import SearchAnalyticsService
from searchat.services.chat_service import generate_rag_response
from searchat.services.export_service import export_conversation
from searchat.api.models.responses import ConversationMessage, ConversationResponse
from searchat.models import SearchMode


def _make_config(tmp_path: Path, *, analytics_enabled: bool = True) -> Mock:
    config = Mock(spec=Config)
    config.paths = Mock()
    config.paths.search_directory = str(tmp_path / ".searchat")
    config.analytics = SimpleNamespace(enabled=analytics_enabled, retention_days=30)
    config.llm = object()
    return config


def test_analytics_30d_queries_under_500ms(tmp_path: Path) -> None:
    config = _make_config(tmp_path)
    service = SearchAnalyticsService(config)

    db_path = service.logs_dir / "analytics.duckdb"
    con = duckdb.connect(str(db_path))
    try:
        # Create a realistic dataset quickly using DuckDB.
        # 150k rows spread over 30 days, multiple tools.
        con.execute(
            """
            INSERT INTO search_history
            SELECT
                'query-' || CAST(i % 5000 AS VARCHAR) AS query,
                CAST(i % 25 AS BIGINT) AS result_count,
                CASE WHEN (i % 3) = 0 THEN 'hybrid' WHEN (i % 3) = 1 THEN 'keyword' ELSE 'semantic' END AS search_mode,
                TIMESTAMP '2026-01-01' + (i % (30*24*60)) * INTERVAL 1 MINUTE AS timestamp,
                CAST(25 + (i % 400) AS BIGINT) AS search_time_ms,
                CASE WHEN (i % 4) = 0 THEN 'all' WHEN (i % 4) = 1 THEN 'claude' WHEN (i % 4) = 2 THEN 'vibe' ELSE 'opencode' END AS tool_filter
            FROM range(150000) t(i)
            """
        )
    finally:
        con.close()

    start = time.perf_counter()
    _ = service.get_trends(days=30)
    _ = service.get_heatmap(days=30)
    _ = service.get_agent_comparison(days=30)
    elapsed_ms = (time.perf_counter() - start) * 1000.0

    assert elapsed_ms < 500.0


def test_rag_internal_overhead_under_200ms(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    config = _make_config(tmp_path, analytics_enabled=False)

    now = datetime.now(timezone.utc)
    results: list[SearchResult] = []
    for i in range(250):
        results.append(
            SearchResult(
                conversation_id=f"c{i}",
                project_id="p",
                title=f"t{i}",
                created_at=now,
                updated_at=now,
                message_count=10,
                file_path=f"/tmp/{i}.jsonl",
                score=1.0,
                snippet="snippet",
                message_start_index=0,
                message_end_index=2,
            )
        )

    search_results = SearchResults(
        results=results,
        total_count=len(results),
        search_time_ms=1.0,
        mode_used="hybrid",
    )

    mock_engine = Mock()
    mock_engine.search.return_value = search_results

    import searchat.services.chat_service as chat_service

    monkeypatch.setattr(chat_service, "get_search_engine", lambda: mock_engine)
    monkeypatch.setattr(chat_service.LLMService, "completion", lambda _self, **_kwargs: "ok")

    start = time.perf_counter()
    gen = generate_rag_response(
        query="Summarize and compare the approaches.",
        provider="ollama",
        model_name=None,
        config=config,
    )
    elapsed_ms = (time.perf_counter() - start) * 1000.0

    assert gen.answer == "ok"
    assert gen.context_used == 16
    assert elapsed_ms < 200.0


def test_export_100_conversations_under_5s() -> None:
    messages: list[ConversationMessage] = []
    now = datetime.now(timezone.utc).isoformat()
    for i in range(10):
        messages.append(ConversationMessage(role="user", content=f"Question {i}\n\n```python\nprint({i})\n```", timestamp=now))
        messages.append(ConversationMessage(role="assistant", content=f"Answer {i}\n\n```python\nprint({i})\n```", timestamp=now))

    start = time.perf_counter()
    for n in range(100):
        conv = ConversationResponse(
            conversation_id=f"conv-{n}",
            title=f"Conversation {n}",
            project_id="proj",
            project_path=None,
            file_path=f"/tmp/conv-{n}.jsonl",
            message_count=len(messages),
            tool="claude",
            messages=messages,
        )
        out = export_conversation(conv, format="markdown")
        assert out.content
    elapsed_s = time.perf_counter() - start
    assert elapsed_s < 5.0


def test_dashboard_render_10_widgets_under_2s(monkeypatch: pytest.MonkeyPatch) -> None:
    from fastapi.testclient import TestClient
    from types import SimpleNamespace

    from searchat.api.app import app
    import searchat.api.routers.dashboards as dashboards_router
    from searchat.models import SearchResult, SearchResults

    class _DashboardsService:
        def __init__(self, dashboard: dict) -> None:
            self._dashboard = dashboard

        def get_dashboard(self, dashboard_id: str):
            if dashboard_id == self._dashboard["id"]:
                return self._dashboard
            return None

    class _SavedQueriesService:
        def __init__(self, queries: dict[str, dict]) -> None:
            self._queries = queries

        def get_query(self, query_id: str):
            return self._queries.get(query_id)

    class _Engine:
        def __init__(self, results: SearchResults) -> None:
            self._results = results

        def search(self, q: str, mode: SearchMode, filters) -> SearchResults:
            return self._results

    widgets = []
    queries = {}
    for i in range(10):
        qid = f"q-{i}"
        widgets.append({"id": f"w-{i}", "query_id": qid, "limit": 5})
        queries[qid] = {
            "id": qid,
            "name": f"Query {i}",
            "query": "deployment",
            "filters": {"project": "proj", "tool": "claude", "sort_by": "relevance"},
            "mode": "keyword",
        }

    dashboard = {
        "id": "dash-1",
        "name": "Perf",
        "description": None,
        "queries": list(queries.keys()),
        "layout": {"widgets": widgets},
        "refresh_interval": None,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }

    now = datetime.now(timezone.utc)
    results = SearchResults(
        results=[
            SearchResult(
                conversation_id="conv-1",
                project_id="proj",
                title="Deploy log",
                created_at=now,
                updated_at=now,
                message_count=4,
                file_path="/tmp/conv.jsonl",
                score=1.0,
                snippet="Deployment steps",
                message_start_index=0,
                message_end_index=1,
            )
        ],
        total_count=1,
        search_time_ms=1.0,
        mode_used="keyword",
    )

    monkeypatch.setattr(
        dashboards_router.deps,
        "get_config",
        lambda: SimpleNamespace(dashboards=SimpleNamespace(enabled=True)),
    )
    monkeypatch.setattr(
        dashboards_router.deps,
        "get_dashboards_service",
        lambda: _DashboardsService(dashboard),
    )
    monkeypatch.setattr(
        dashboards_router.deps,
        "get_saved_queries_service",
        lambda: _SavedQueriesService(queries),
    )
    monkeypatch.setattr(dashboards_router, "get_or_create_search_engine", lambda: _Engine(results))

    client = TestClient(app)
    start = time.perf_counter()
    response = client.get("/api/dashboards/dash-1/render")
    elapsed_ms = (time.perf_counter() - start) * 1000.0

    assert response.status_code == 200
    assert elapsed_ms < 2000.0
