from __future__ import annotations

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import Mock

import duckdb
import pytest

from searchat.config import Config
from searchat.services.analytics import SearchAnalyticsService


@pytest.fixture
def mock_config(tmp_path):
    config = Mock(spec=Config)
    config.paths = Mock()
    config.paths.search_directory = str(tmp_path / ".searchat")
    config.analytics = SimpleNamespace(enabled=True, retention_days=30)
    return config


@pytest.fixture
def analytics_service(mock_config):
    return SearchAnalyticsService(mock_config)


def _count_rows(db_path: str) -> int:
    con = duckdb.connect(db_path, read_only=True)
    try:
        row = con.execute("SELECT COUNT(*) FROM search_history").fetchone()
        assert row is not None
        return int(row[0])
    finally:
        con.close()


def test_analytics_service_initialization_creates_db(analytics_service):
    db_path = str(analytics_service.logs_dir / "analytics.duckdb")
    assert (analytics_service.logs_dir / "analytics.duckdb").exists()
    assert _count_rows(db_path) == 0


def test_log_search_inserts_row(analytics_service):
    analytics_service.log_search(
        query="python testing",
        result_count=10,
        search_mode="hybrid",
        search_time_ms=123,
        tool_filter="claude",
    )
    db_path = str(analytics_service.logs_dir / "analytics.duckdb")
    assert _count_rows(db_path) == 1


def test_log_search_respects_opt_in(tmp_path):
    config = Mock(spec=Config)
    config.paths = Mock()
    config.paths.search_directory = str(tmp_path / ".searchat")
    config.analytics = SimpleNamespace(enabled=False, retention_days=30)
    service = SearchAnalyticsService(config)

    service.log_search(
        query="x",
        result_count=0,
        search_mode="hybrid",
        search_time_ms=1,
        tool_filter="all",
    )

    db_path = str(service.logs_dir / "analytics.duckdb")
    assert _count_rows(db_path) == 0


def test_get_stats_summary_and_top_queries(analytics_service):
    for _ in range(3):
        analytics_service.log_search(
            query="python",
            result_count=5,
            search_mode="hybrid",
            search_time_ms=100,
            tool_filter="all",
        )
    analytics_service.log_search(
        query="javascript",
        result_count=1,
        search_mode="keyword",
        search_time_ms=50,
        tool_filter="opencode",
    )

    summary = analytics_service.get_stats_summary(days=7)
    assert summary["total_searches"] == 4
    assert summary["unique_queries"] == 2
    assert "mode_distribution" in summary
    assert summary["mode_distribution"]["hybrid"] == 3
    assert summary["mode_distribution"]["keyword"] == 1

    top = analytics_service.get_top_queries(limit=2, days=7)
    assert top[0]["query"] == "python"
    assert top[0]["search_count"] == 3


def test_retention_deletes_old_rows(tmp_path):
    config = Mock(spec=Config)
    config.paths = Mock()
    config.paths.search_directory = str(tmp_path / ".searchat")
    config.analytics = SimpleNamespace(enabled=True, retention_days=1)
    service = SearchAnalyticsService(config)

    db_path = str(service.logs_dir / "analytics.duckdb")
    con = duckdb.connect(db_path)
    try:
        con.execute(
            """
            INSERT INTO search_history (query, result_count, search_mode, timestamp, search_time_ms, tool_filter)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            [
                "old",
                0,
                "hybrid",
                datetime.now(timezone.utc) - timedelta(days=10),
                1,
                "all",
            ],
        )
    finally:
        con.close()

    service.log_search(
        query="new",
        result_count=1,
        search_mode="hybrid",
        search_time_ms=1,
        tool_filter="all",
    )

    assert _count_rows(db_path) == 1


def test_trends_heatmap_and_agent_comparison(tmp_path):
    config = Mock(spec=Config)
    config.paths = Mock()
    config.paths.search_directory = str(tmp_path / ".searchat")
    config.analytics = SimpleNamespace(enabled=True, retention_days=30)
    service = SearchAnalyticsService(config)

    db_path = str(service.logs_dir / "analytics.duckdb")
    con = duckdb.connect(db_path)
    try:
        con.execute(
            """
            INSERT INTO search_history (query, result_count, search_mode, timestamp, search_time_ms, tool_filter)
            VALUES
                ('a', 1, 'hybrid', ?, 10, 'claude'),
                ('b', 2, 'keyword', ?, 20, 'opencode')
            """,
            [
                datetime(2026, 1, 1, 10, 0, tzinfo=timezone.utc),
                datetime(2026, 1, 2, 11, 0, tzinfo=timezone.utc),
            ],
        )
    finally:
        con.close()

    trends = service.get_trends(days=365)
    assert len(trends) >= 2
    assert trends[0]["day"] == "2026-01-01"

    heatmap = service.get_heatmap(days=365)
    assert heatmap["days"] == 365
    assert any(c["searches"] >= 1 for c in heatmap["cells"])

    tools = service.get_agent_comparison(days=365)
    tool_names = {t["tool_filter"] for t in tools}
    assert "claude" in tool_names
    assert "opencode" in tool_names


def test_topic_clusters_returns_clusters(tmp_path):
    config = Mock(spec=Config)
    config.paths = Mock()
    config.paths.search_directory = str(tmp_path / ".searchat")
    config.analytics = SimpleNamespace(enabled=True, retention_days=30)
    service = SearchAnalyticsService(config)

    for i in range(12):
        service.log_search(
            query=f"python error {i}",
            result_count=1,
            search_mode="hybrid",
            search_time_ms=10,
            tool_filter="all",
        )
        service.log_search(
            query=f"javascript async {i}",
            result_count=1,
            search_mode="hybrid",
            search_time_ms=10,
            tool_filter="all",
        )

    clusters = service.get_topic_clusters(days=7, k=8)
    assert clusters
    assert all("cluster_id" in c for c in clusters)
