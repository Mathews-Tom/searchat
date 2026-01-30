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
