"""API tests for analytics routes."""
from __future__ import annotations

import pytest
from unittest.mock import Mock, patch
from fastapi.testclient import TestClient

from searchat.api.app import app


@pytest.fixture
def client():
    """FastAPI test client."""
    return TestClient(app)


@pytest.fixture
def mock_analytics_service():
    """Mock SearchAnalyticsService."""
    mock = Mock()

    # Mock get_stats_summary
    mock.get_stats_summary.return_value = {
        'total_searches': 100,
        'unique_queries': 50,
        'avg_results': 12.5,
        'avg_time_ms': 150.0,
        'mode_distribution': {
            'hybrid': 60,
            'semantic': 30,
            'keyword': 10
        }
    }

    # Mock get_top_queries
    mock.get_top_queries.return_value = [
        {
            'query': 'python testing',
            'search_count': 15,
            'avg_results': 20.0,
            'avg_time_ms': 120.0
        },
        {
            'query': 'javascript async',
            'search_count': 10,
            'avg_results': 15.0,
            'avg_time_ms': 100.0
        }
    ]

    # Mock get_dead_end_queries
    mock.get_dead_end_queries.return_value = [
        {
            'query': 'obscure query',
            'search_count': 5,
            'avg_results': 0.5
        },
        {
            'query': 'rare term',
            'search_count': 3,
            'avg_results': 2.0
        }
    ]

    mock.get_trends.return_value = [
        {"day": "2026-01-01", "searches": 3, "unique_queries": 2, "avg_time_ms": 100.0, "avg_results": 5.0},
    ]
    mock.get_heatmap.return_value = {"days": 30, "cells": [{"dow": 1, "hour": 9, "searches": 2}]}
    mock.get_agent_comparison.return_value = [
        {"tool_filter": "all", "searches": 10, "avg_time_ms": 120.0, "avg_results": 8.0},
    ]
    mock.get_topic_clusters.return_value = [
        {
            "cluster_id": 0,
            "searches": 10,
            "representative_query": "python",
            "top_terms": ["python"],
            "examples": ["python"],
        }
    ]

    return mock


def test_get_analytics_summary(client, mock_analytics_service):
    """Test GET /api/stats/analytics/summary."""
    with patch("searchat.api.dependencies.get_analytics_service", return_value=mock_analytics_service):
        response = client.get("/api/stats/analytics/summary")

        assert response.status_code == 200
        data = response.json()

        assert data['total_searches'] == 100
        assert data['unique_queries'] == 50
        assert data['avg_results'] == 12.5
        assert data['avg_time_ms'] == 150.0
        assert data['mode_distribution']['hybrid'] == 60

        # Verify service was called with default days=7
        mock_analytics_service.get_stats_summary.assert_called_once_with(days=7)


def test_get_analytics_summary_with_days_param(client, mock_analytics_service):
    """Test GET /api/stats/analytics/summary with custom days parameter."""
    with patch("searchat.api.dependencies.get_analytics_service", return_value=mock_analytics_service):
        response = client.get("/api/stats/analytics/summary?days=30")

        assert response.status_code == 200

        # Verify service was called with days=30
        mock_analytics_service.get_stats_summary.assert_called_once_with(days=30)


def test_get_analytics_summary_days_validation(client, mock_analytics_service):
    """Test days parameter validation for summary endpoint."""
    with patch("searchat.api.dependencies.get_analytics_service", return_value=mock_analytics_service):
        # days < 1 should fail
        response = client.get("/api/stats/analytics/summary?days=0")
        assert response.status_code == 422

        # days > 90 should fail
        response = client.get("/api/stats/analytics/summary?days=91")
        assert response.status_code == 422

        # Valid range should pass
        response = client.get("/api/stats/analytics/summary?days=30")
        assert response.status_code == 200


def test_get_top_queries(client, mock_analytics_service):
    """Test GET /api/stats/analytics/top-queries."""
    with patch("searchat.api.dependencies.get_analytics_service", return_value=mock_analytics_service):
        response = client.get("/api/stats/analytics/top-queries")

        assert response.status_code == 200
        data = response.json()

        assert 'queries' in data
        assert 'days' in data
        assert len(data['queries']) == 2

        query1 = data['queries'][0]
        assert query1['query'] == 'python testing'
        assert query1['search_count'] == 15
        assert query1['avg_results'] == 20.0

        # Verify service was called with defaults
        mock_analytics_service.get_top_queries.assert_called_once_with(limit=10, days=7)


def test_get_top_queries_with_params(client, mock_analytics_service):
    """Test GET /api/stats/analytics/top-queries with custom parameters."""
    with patch("searchat.api.dependencies.get_analytics_service", return_value=mock_analytics_service):
        response = client.get("/api/stats/analytics/top-queries?limit=20&days=30")

        assert response.status_code == 200

        # Verify service was called with custom params
        mock_analytics_service.get_top_queries.assert_called_once_with(limit=20, days=30)


def test_get_top_queries_limit_validation(client, mock_analytics_service):
    """Test limit parameter validation for top-queries endpoint."""
    with patch("searchat.api.dependencies.get_analytics_service", return_value=mock_analytics_service):
        # limit < 1 should fail
        response = client.get("/api/stats/analytics/top-queries?limit=0")
        assert response.status_code == 422

        # limit > 50 should fail
        response = client.get("/api/stats/analytics/top-queries?limit=51")
        assert response.status_code == 422

        # Valid range should pass
        response = client.get("/api/stats/analytics/top-queries?limit=25")
        assert response.status_code == 200


def test_get_dead_end_queries(client, mock_analytics_service):
    """Test GET /api/stats/analytics/dead-ends."""
    with patch("searchat.api.dependencies.get_analytics_service", return_value=mock_analytics_service):
        response = client.get("/api/stats/analytics/dead-ends")

        assert response.status_code == 200
        data = response.json()

        assert 'queries' in data
        assert 'days' in data
        assert len(data['queries']) == 2

        query1 = data['queries'][0]
        assert query1['query'] == 'obscure query'
        assert query1['search_count'] == 5
        assert query1['avg_results'] == 0.5

        # Verify service was called with defaults
        mock_analytics_service.get_dead_end_queries.assert_called_once_with(limit=10, days=7)


def test_get_dead_end_queries_with_params(client, mock_analytics_service):
    """Test GET /api/stats/analytics/dead-ends with custom parameters."""
    with patch("searchat.api.dependencies.get_analytics_service", return_value=mock_analytics_service):
        response = client.get("/api/stats/analytics/dead-ends?limit=20&days=14")

        assert response.status_code == 200

        # Verify service was called with custom params
        mock_analytics_service.get_dead_end_queries.assert_called_once_with(limit=20, days=14)


def test_analytics_empty_data(client, mock_analytics_service):
    """Test analytics endpoints handle empty data correctly."""
    # Mock empty data
    mock_analytics_service.get_stats_summary.return_value = {
        'total_searches': 0,
        'unique_queries': 0,
        'avg_results': 0,
        'avg_time_ms': 0,
        'mode_distribution': {}
    }
    mock_analytics_service.get_top_queries.return_value = []
    mock_analytics_service.get_dead_end_queries.return_value = []

    with patch("searchat.api.dependencies.get_analytics_service", return_value=mock_analytics_service):
        # Summary with no data
        response = client.get("/api/stats/analytics/summary")
        assert response.status_code == 200
        data = response.json()
        assert data['total_searches'] == 0

        # Top queries with no data
        response = client.get("/api/stats/analytics/top-queries")
        assert response.status_code == 200
        data = response.json()
        assert data['queries'] == []

        # Dead ends with no data
        response = client.get("/api/stats/analytics/dead-ends")
        assert response.status_code == 200
        data = response.json()
        assert data['queries'] == []


def test_analytics_service_error_handling(client, mock_analytics_service):
    """Test analytics endpoints handle service errors."""
    # Mock service to raise exception
    mock_analytics_service.get_stats_summary.side_effect = Exception("Database error")

    with patch("searchat.api.dependencies.get_analytics_service", return_value=mock_analytics_service):
        response = client.get("/api/stats/analytics/summary")

        # Should return 500 error
        assert response.status_code == 500


def test_analytics_new_endpoints_error_handling(client, mock_analytics_service):
    mock_analytics_service.get_trends.side_effect = Exception("boom")
    mock_analytics_service.get_heatmap.side_effect = Exception("boom")
    mock_analytics_service.get_agent_comparison.side_effect = Exception("boom")
    mock_analytics_service.get_topic_clusters.side_effect = Exception("boom")

    with patch("searchat.api.dependencies.get_analytics_service", return_value=mock_analytics_service):
        assert client.get("/api/stats/analytics/trends").status_code == 500
        assert client.get("/api/stats/analytics/heatmap").status_code == 500
        assert client.get("/api/stats/analytics/agent-comparison").status_code == 500
        assert client.get("/api/stats/analytics/topics").status_code == 500


def test_analytics_topics_value_error_returns_400(client, mock_analytics_service):
    mock_analytics_service.get_topic_clusters.side_effect = ValueError("k must be between 2 and 20")
    with patch("searchat.api.dependencies.get_analytics_service", return_value=mock_analytics_service):
        resp = client.get("/api/stats/analytics/topics?days=30&k=8")
        assert resp.status_code == 400


def test_analytics_config_error_handling(client, mock_analytics_service):
    with patch("searchat.api.dependencies.get_analytics_service", return_value=mock_analytics_service), \
         patch("searchat.api.routers.stats.deps.get_config", side_effect=Exception("boom")):
        resp = client.get("/api/stats/analytics/config")
        assert resp.status_code == 500


def test_all_analytics_endpoints_exist(client, mock_analytics_service):
    """Test all analytics endpoints are registered."""
    with patch("searchat.api.dependencies.get_analytics_service", return_value=mock_analytics_service), \
         patch("searchat.api.routers.stats.deps.get_config") as mock_get_config:
        mock_get_config.return_value = Mock(analytics=Mock(enabled=False, retention_days=30))
        endpoints = [
            "/api/stats/analytics/summary",
            "/api/stats/analytics/top-queries",
            "/api/stats/analytics/dead-ends",
            "/api/stats/analytics/config",
            "/api/stats/analytics/trends",
            "/api/stats/analytics/heatmap",
            "/api/stats/analytics/agent-comparison",
            "/api/stats/analytics/topics",
        ]

        for endpoint in endpoints:
            response = client.get(endpoint)
            # Should not be 404 (endpoint exists)
            assert response.status_code != 404


def test_get_analytics_trends(client, mock_analytics_service):
    with patch("searchat.api.dependencies.get_analytics_service", return_value=mock_analytics_service):
        response = client.get("/api/stats/analytics/trends?days=30")
        assert response.status_code == 200
        data = response.json()
        assert data["days"] == 30
        assert data["points"][0]["day"] == "2026-01-01"
        mock_analytics_service.get_trends.assert_called_once_with(days=30)


def test_get_analytics_heatmap(client, mock_analytics_service):
    with patch("searchat.api.dependencies.get_analytics_service", return_value=mock_analytics_service):
        response = client.get("/api/stats/analytics/heatmap?days=30")
        assert response.status_code == 200
        data = response.json()
        assert data["days"] == 30
        assert "cells" in data
        mock_analytics_service.get_heatmap.assert_called_once_with(days=30)


def test_get_analytics_agent_comparison(client, mock_analytics_service):
    with patch("searchat.api.dependencies.get_analytics_service", return_value=mock_analytics_service):
        response = client.get("/api/stats/analytics/agent-comparison?days=30")
        assert response.status_code == 200
        data = response.json()
        assert data["days"] == 30
        assert data["tools"][0]["tool_filter"] == "all"
        mock_analytics_service.get_agent_comparison.assert_called_once_with(days=30)


def test_get_analytics_topics(client, mock_analytics_service):
    with patch("searchat.api.dependencies.get_analytics_service", return_value=mock_analytics_service):
        response = client.get("/api/stats/analytics/topics?days=30&k=8")
        assert response.status_code == 200
        data = response.json()
        assert data["days"] == 30
        assert len(data["clusters"]) == 1
        mock_analytics_service.get_topic_clusters.assert_called_once_with(days=30, k=8)


def test_get_analytics_config(client, mock_analytics_service):
    with patch("searchat.api.dependencies.get_analytics_service", return_value=mock_analytics_service), \
         patch("searchat.api.routers.stats.deps.get_config") as mock_get_config:
        mock_get_config.return_value = Mock(analytics=Mock(enabled=True, retention_days=14))
        response = client.get("/api/stats/analytics/config")
        assert response.status_code == 200
        data = response.json()
        assert data["enabled"] is True
        assert data["retention_days"] == 14


def test_analytics_endpoints_reject_snapshot_mode(client):
    endpoints = [
        "/api/stats/analytics/summary",
        "/api/stats/analytics/top-queries",
        "/api/stats/analytics/dead-ends",
        "/api/stats/analytics/config",
        "/api/stats/analytics/trends",
        "/api/stats/analytics/heatmap",
        "/api/stats/analytics/agent-comparison",
        "/api/stats/analytics/topics",
    ]
    for endpoint in endpoints:
        resp = client.get(f"{endpoint}?snapshot=backup_20250101_000000")
        assert resp.status_code == 403
        assert "active dataset" in resp.json()["detail"].lower()
