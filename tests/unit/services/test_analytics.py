"""Unit tests for SearchAnalyticsService."""
from __future__ import annotations

import pytest
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import Mock
import pyarrow as pa
import pyarrow.parquet as pq

from searchat.services.analytics import SearchAnalyticsService
from searchat.config import Config


@pytest.fixture
def mock_config(tmp_path):
    """Create mock config with temporary paths."""
    config = Mock(spec=Config)
    config.paths = Mock()
    config.paths.search_directory = str(tmp_path / ".searchat")
    return config


@pytest.fixture
def analytics_service(mock_config):
    """Create SearchAnalyticsService with mock config."""
    service = SearchAnalyticsService(mock_config)
    # Ensure logs directory exists
    service.logs_dir.mkdir(parents=True, exist_ok=True)
    return service


def test_analytics_service_initialization(analytics_service):
    """Test SearchAnalyticsService initializes correctly."""
    assert analytics_service.logs_dir.exists()
    assert analytics_service.schema is not None
    assert len(analytics_service.schema) == 5  # 5 fields


def test_log_search_creates_file(analytics_service):
    """Test log_search creates a Parquet file."""
    analytics_service.log_search(
        query="test query",
        result_count=10,
        search_mode="hybrid",
        search_time_ms=150
    )

    # Check file was created
    today = datetime.now().date()
    log_file = analytics_service.logs_dir / f"search_logs_{today.isoformat()}.parquet"
    assert log_file.exists()


def test_log_search_writes_correct_data(analytics_service):
    """Test log_search writes correct data to Parquet."""
    test_query = "python testing"
    test_count = 25
    test_mode = "semantic"
    test_time = 200

    analytics_service.log_search(
        query=test_query,
        result_count=test_count,
        search_mode=test_mode,
        search_time_ms=test_time
    )

    # Read the file and verify
    today = datetime.now().date()
    log_file = analytics_service.logs_dir / f"search_logs_{today.isoformat()}.parquet"
    table = pq.read_table(log_file)

    assert len(table) == 1
    assert table['query'][0].as_py() == test_query
    assert table['result_count'][0].as_py() == test_count
    assert table['search_mode'][0].as_py() == test_mode
    assert table['search_time_ms'][0].as_py() == test_time


def test_log_search_appends_to_existing_file(analytics_service):
    """Test log_search appends to existing file instead of overwriting."""
    # Log first search
    analytics_service.log_search("query1", 5, "hybrid", 100)

    # Log second search
    analytics_service.log_search("query2", 10, "keyword", 150)

    # Read the file and verify both entries
    today = datetime.now().date()
    log_file = analytics_service.logs_dir / f"search_logs_{today.isoformat()}.parquet"
    table = pq.read_table(log_file)

    assert len(table) == 2
    assert table['query'][0].as_py() == "query1"
    assert table['query'][1].as_py() == "query2"


def test_rotate_old_logs_deletes_old_files(analytics_service):
    """Test _rotate_old_logs deletes files older than 30 days."""
    # Create old log file (40 days ago)
    old_date = (datetime.now() - timedelta(days=40)).date()
    old_file = analytics_service.logs_dir / f"search_logs_{old_date.isoformat()}.parquet"

    # Create a dummy Parquet file
    table = pa.table({
        'query': ['old query'],
        'result_count': [1],
        'search_mode': ['hybrid'],
        'timestamp': [datetime.now()],
        'search_time_ms': [100],
    }, schema=analytics_service.schema)
    pq.write_table(table, old_file)

    # Create recent log file (5 days ago)
    recent_date = (datetime.now() - timedelta(days=5)).date()
    recent_file = analytics_service.logs_dir / f"search_logs_{recent_date.isoformat()}.parquet"
    pq.write_table(table, recent_file)

    # Verify both files exist
    assert old_file.exists()
    assert recent_file.exists()

    # Run rotation
    analytics_service._rotate_old_logs()

    # Old file should be deleted, recent file should remain
    assert not old_file.exists()
    assert recent_file.exists()


def test_rotate_old_logs_ignores_invalid_filenames(analytics_service):
    """Test _rotate_old_logs ignores files with invalid names."""
    # Create file with invalid name
    invalid_file = analytics_service.logs_dir / "invalid_name.parquet"
    invalid_file.touch()

    # Run rotation (should not crash)
    analytics_service._rotate_old_logs()

    # Invalid file should still exist (not deleted)
    assert invalid_file.exists()


def test_get_top_queries_empty(analytics_service):
    """Test get_top_queries with no data returns empty list."""
    result = analytics_service.get_top_queries(limit=10, days=7)
    assert result == []


def test_get_top_queries_returns_correct_data(analytics_service):
    """Test get_top_queries returns aggregated data."""
    # Log multiple searches
    analytics_service.log_search("python", 10, "hybrid", 100)
    analytics_service.log_search("python", 12, "hybrid", 110)
    analytics_service.log_search("javascript", 5, "semantic", 200)

    result = analytics_service.get_top_queries(limit=10, days=7)

    assert len(result) == 2

    # Python should be first (2 searches)
    assert result[0]['query'] == "python"
    assert result[0]['search_count'] == 2
    assert result[0]['avg_results'] == 11.0  # (10 + 12) / 2
    assert result[0]['avg_time_ms'] == 105.0  # (100 + 110) / 2

    # JavaScript should be second (1 search)
    assert result[1]['query'] == "javascript"
    assert result[1]['search_count'] == 1


def test_get_top_queries_respects_limit(analytics_service):
    """Test get_top_queries respects limit parameter."""
    # Log searches for multiple queries
    for i in range(5):
        analytics_service.log_search(f"query{i}", 10, "hybrid", 100)

    result = analytics_service.get_top_queries(limit=3, days=7)

    assert len(result) == 3


def test_get_top_queries_filters_empty_and_wildcard(analytics_service):
    """Test get_top_queries filters out empty queries and wildcards."""
    analytics_service.log_search("", 10, "hybrid", 100)
    analytics_service.log_search("*", 10, "keyword", 100)
    analytics_service.log_search("valid query", 10, "hybrid", 100)

    result = analytics_service.get_top_queries(limit=10, days=7)

    assert len(result) == 1
    assert result[0]['query'] == "valid query"


def test_get_stats_summary_empty(analytics_service):
    """Test get_stats_summary with no data."""
    result = analytics_service.get_stats_summary(days=7)

    assert result['total_searches'] == 0
    assert result['unique_queries'] == 0
    assert result['avg_results'] == 0
    assert result['avg_time_ms'] == 0
    assert result['mode_distribution'] == {}


def test_get_stats_summary_returns_correct_stats(analytics_service):
    """Test get_stats_summary calculates correct statistics."""
    # Log various searches
    analytics_service.log_search("query1", 10, "hybrid", 100)
    analytics_service.log_search("query2", 20, "semantic", 150)
    analytics_service.log_search("query1", 15, "hybrid", 120)  # Duplicate query
    analytics_service.log_search("query3", 5, "keyword", 80)

    result = analytics_service.get_stats_summary(days=7)

    assert result['total_searches'] == 4
    assert result['unique_queries'] == 3  # query1, query2, query3
    assert result['avg_results'] == 12.5  # (10 + 20 + 15 + 5) / 4
    assert result['avg_time_ms'] == 112.5  # (100 + 150 + 120 + 80) / 4

    # Check mode distribution
    assert result['mode_distribution']['hybrid'] == 2
    assert result['mode_distribution']['semantic'] == 1
    assert result['mode_distribution']['keyword'] == 1


def test_get_dead_end_queries_empty(analytics_service):
    """Test get_dead_end_queries with no data."""
    result = analytics_service.get_dead_end_queries(limit=10, days=7)
    assert result == []


def test_get_dead_end_queries_returns_low_results(analytics_service):
    """Test get_dead_end_queries returns queries with 3 or fewer results."""
    # Log searches with various result counts
    analytics_service.log_search("no results", 0, "hybrid", 100)
    analytics_service.log_search("one result", 1, "semantic", 100)
    analytics_service.log_search("three results", 3, "hybrid", 100)
    analytics_service.log_search("many results", 10, "hybrid", 100)

    result = analytics_service.get_dead_end_queries(limit=10, days=7)

    # Should only include queries with <= 3 results
    assert len(result) == 3
    query_names = [r['query'] for r in result]
    assert "no results" in query_names
    assert "one result" in query_names
    assert "three results" in query_names
    assert "many results" not in query_names


def test_get_dead_end_queries_sorts_by_search_count(analytics_service):
    """Test get_dead_end_queries sorts by search count descending."""
    # Log searches with different frequencies
    analytics_service.log_search("rare", 0, "hybrid", 100)
    analytics_service.log_search("common", 1, "hybrid", 100)
    analytics_service.log_search("common", 2, "hybrid", 100)
    analytics_service.log_search("common", 0, "hybrid", 100)

    result = analytics_service.get_dead_end_queries(limit=10, days=7)

    # "common" appears 3 times, should be first
    assert result[0]['query'] == "common"
    assert result[0]['search_count'] == 3


def test_get_dead_end_queries_filters_empty_and_wildcard(analytics_service):
    """Test get_dead_end_queries filters out empty and wildcard queries."""
    analytics_service.log_search("", 0, "hybrid", 100)
    analytics_service.log_search("*", 1, "keyword", 100)
    analytics_service.log_search("valid", 2, "hybrid", 100)

    result = analytics_service.get_dead_end_queries(limit=10, days=7)

    assert len(result) == 1
    assert result[0]['query'] == "valid"


def test_analytics_respects_days_parameter(analytics_service):
    """Test analytics methods respect the days parameter."""
    # Create old log file (10 days ago)
    old_date = (datetime.now() - timedelta(days=10)).date()
    old_file = analytics_service.logs_dir / f"search_logs_{old_date.isoformat()}.parquet"

    table = pa.table({
        'query': ['old query'],
        'result_count': [10],
        'search_mode': ['hybrid'],
        'timestamp': [datetime.now() - timedelta(days=10)],
        'search_time_ms': [100],
    }, schema=analytics_service.schema)
    pq.write_table(table, old_file)

    # Log recent search
    analytics_service.log_search("recent query", 10, "hybrid", 100)

    # Query with days=7 should only include recent search
    result = analytics_service.get_top_queries(limit=10, days=7)
    assert len(result) == 1
    assert result[0]['query'] == "recent query"

    # Query with days=30 should include both
    result = analytics_service.get_top_queries(limit=10, days=30)
    assert len(result) == 2


def test_schema_validation(analytics_service):
    """Test Parquet schema has correct field types."""
    schema = analytics_service.schema

    assert schema.field('query').type == pa.string()
    assert schema.field('result_count').type == pa.int64()
    assert schema.field('search_mode').type == pa.string()
    assert schema.field('timestamp').type == pa.timestamp('us')
    assert schema.field('search_time_ms').type == pa.int64()
