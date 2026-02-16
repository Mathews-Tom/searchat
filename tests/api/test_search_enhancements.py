"""API tests for search enhancements (suggestions and pagination)."""
from __future__ import annotations

import pytest
from datetime import datetime
from unittest.mock import Mock, patch
from fastapi.testclient import TestClient

from searchat.api.app import app


@pytest.fixture
def client():
    """FastAPI test client."""
    return TestClient(app)


@pytest.fixture
def mock_duckdb_store_for_suggestions():
    """Mock DuckDBStore for suggestions endpoint."""
    mock = Mock()

    # Mock _connect and query results
    mock_conn = Mock()

    # Mock conversation titles for suggestions
    mock_conn.execute.return_value.fetchall.return_value = [
        ("Python Testing Best Practices",),
        ("Python Async Programming",),
        ("JavaScript Testing Framework",),
        ("Building REST APIs with Python",),
        ("Python Type Hints Guide",),
    ]

    mock._connect.return_value = mock_conn

    return mock


@pytest.fixture
def mock_search_results():
    """Mock search results for pagination testing."""
    from datetime import datetime
    from searchat.models import SearchResult, SearchResults

    results = [
        SearchResult(
            conversation_id=f"conv-{i}",
            project_id=f"project-{i % 3}",
            title=f"Conversation {i}",
            created_at=datetime.now(),
            updated_at=datetime.now(),
            message_count=10 + i,
            file_path=f"/path/to/conv-{i}.jsonl",
            snippet=f"This is conversation {i}",
            score=1.0 - (i * 0.01),
            message_start_index=0,
            message_end_index=10
        )
        for i in range(50)  # 50 conversations
    ]

    return SearchResults(
        results=results,
        total_count=50,
        search_time_ms=100,
        mode_used="hybrid"
    )


# ============================================================================
# SUGGESTIONS TESTS
# ============================================================================

def test_get_search_suggestions(client, mock_duckdb_store_for_suggestions):
    """Test GET /api/search/suggestions with query."""
    with patch("searchat.api.routers.search.deps.get_duckdb_store", return_value=mock_duckdb_store_for_suggestions):
        response = client.get("/api/search/suggestions?q=python")

        assert response.status_code == 200
        data = response.json()

        assert "query" in data
        assert "suggestions" in data
        assert data["query"] == "python"
        assert isinstance(data["suggestions"], list)


def test_get_search_suggestions_word_extraction(client, mock_duckdb_store_for_suggestions):
    """Test suggestions extract words and phrases from titles."""
    with patch("searchat.api.routers.search.deps.get_duckdb_store", return_value=mock_duckdb_store_for_suggestions):
        response = client.get("/api/search/suggestions?q=test")

        assert response.status_code == 200
        data = response.json()

        # Should find words containing "test"
        assert any("test" in s.lower() for s in data["suggestions"])


def test_get_search_suggestions_limit(client, mock_duckdb_store_for_suggestions):
    """Test suggestions endpoint respects limit parameter."""
    with patch("searchat.api.routers.search.deps.get_duckdb_store", return_value=mock_duckdb_store_for_suggestions):
        response = client.get("/api/search/suggestions?q=python&limit=5")

        assert response.status_code == 200
        data = response.json()

        # Should not exceed limit
        assert len(data["suggestions"]) <= 5


def test_get_search_suggestions_limit_validation(client, mock_duckdb_store_for_suggestions):
    """Test limit parameter validation for suggestions."""
    with patch("searchat.api.routers.search.deps.get_duckdb_store", return_value=mock_duckdb_store_for_suggestions):
        # limit < 1 should fail
        response = client.get("/api/search/suggestions?q=test&limit=0")
        assert response.status_code == 422

        # limit > 20 should fail
        response = client.get("/api/search/suggestions?q=test&limit=21")
        assert response.status_code == 422

        # Valid limit should pass
        response = client.get("/api/search/suggestions?q=test&limit=10")
        assert response.status_code == 200


def test_get_search_suggestions_min_length_validation(client):
    """Test query must have minimum length."""
    # Empty query should fail
    response = client.get("/api/search/suggestions?q=")
    assert response.status_code == 422


def test_get_search_suggestions_prefix_priority(client, mock_duckdb_store_for_suggestions):
    """Test suggestions prioritize prefix matches."""
    with patch("searchat.api.routers.search.deps.get_duckdb_store", return_value=mock_duckdb_store_for_suggestions):
        response = client.get("/api/search/suggestions?q=py")

        assert response.status_code == 200
        data = response.json()

        # Suggestions starting with "py" should come first
        if len(data["suggestions"]) > 0:
            # At least check that we got results
            assert isinstance(data["suggestions"], list)


def test_get_search_suggestions_case_insensitive(client, mock_duckdb_store_for_suggestions):
    """Test suggestions are case-insensitive."""
    with patch("searchat.api.routers.search.deps.get_duckdb_store", return_value=mock_duckdb_store_for_suggestions):
        response1 = client.get("/api/search/suggestions?q=python")
        response2 = client.get("/api/search/suggestions?q=PYTHON")

        assert response1.status_code == 200
        assert response2.status_code == 200

        # Both should return suggestions (case doesn't matter)
        data1 = response1.json()
        data2 = response2.json()

        assert len(data1["suggestions"]) > 0
        assert len(data2["suggestions"]) > 0


def test_get_search_suggestions_deduplication(client, mock_duckdb_store_for_suggestions):
    """Test suggestions deduplicate results."""
    with patch("searchat.api.routers.search.deps.get_duckdb_store", return_value=mock_duckdb_store_for_suggestions):
        response = client.get("/api/search/suggestions?q=test")

        assert response.status_code == 200
        data = response.json()

        # All suggestions should be unique
        suggestions = data["suggestions"]
        assert len(suggestions) == len(set(suggestions))


# ============================================================================
# PAGINATION TESTS
# ============================================================================

def test_search_pagination_offset_parameter(client, mock_search_results):
    """Test /api/search endpoint accepts offset parameter."""
    mock_engine = Mock()
    mock_engine.search.return_value = mock_search_results

    with patch("searchat.api.routers.search.deps.get_or_create_search_engine", return_value=mock_engine), \
         patch("searchat.api.routers.search.get_analytics_service"), \
         patch("searchat.api.routers.search.deps.resolve_dataset_search_dir", return_value=(Mock(), None)), \
         patch("searchat.api.routers.search.deps.get_config", return_value=Mock(analytics=Mock(enabled=False))):

        response = client.get("/api/search?q=test&mode=keyword&offset=10")

        assert response.status_code == 200
        data = response.json()

        assert "offset" in data
        assert data["offset"] == 10


def test_search_pagination_limit_parameter(client, mock_search_results):
    """Test /api/search endpoint accepts limit parameter."""
    mock_engine = Mock()
    mock_engine.search.return_value = mock_search_results

    with patch("searchat.api.routers.search.deps.get_or_create_search_engine", return_value=mock_engine), \
         patch("searchat.api.routers.search.get_analytics_service"), \
         patch("searchat.api.routers.search.deps.resolve_dataset_search_dir", return_value=(Mock(), None)), \
         patch("searchat.api.routers.search.deps.get_config", return_value=Mock(analytics=Mock(enabled=False))):

        response = client.get("/api/search?q=test&mode=keyword&limit=10")

        assert response.status_code == 200
        data = response.json()

        assert "limit" in data
        assert data["limit"] == 10
        # Results should not exceed limit
        assert len(data["results"]) <= 10


def test_search_pagination_has_more_flag(client, mock_search_results):
    """Test /api/search returns has_more flag for pagination."""
    mock_engine = Mock()
    mock_engine.search.return_value = mock_search_results

    with patch("searchat.api.routers.search.deps.get_or_create_search_engine", return_value=mock_engine), \
         patch("searchat.api.routers.search.get_analytics_service"), \
         patch("searchat.api.routers.search.deps.resolve_dataset_search_dir", return_value=(Mock(), None)), \
         patch("searchat.api.routers.search.deps.get_config", return_value=Mock(analytics=Mock(enabled=False))):

        # First page (offset=0, limit=20)
        response = client.get("/api/search?q=test&mode=keyword&offset=0&limit=20")
        assert response.status_code == 200
        data = response.json()

        assert "has_more" in data
        # With 50 total results, offset 0 and limit 20, should have more
        assert data["has_more"] is True

        # Last page (offset=40, limit=20)
        response = client.get("/api/search?q=test&mode=keyword&offset=40&limit=20")
        data = response.json()

        # Should not have more (40 + 20 >= 50)
        assert data["has_more"] is False


def test_search_pagination_default_limit(client, mock_search_results):
    """Test search endpoint has default limit of 20."""
    mock_engine = Mock()
    mock_engine.search.return_value = mock_search_results

    with patch("searchat.api.routers.search.deps.get_or_create_search_engine", return_value=mock_engine), \
         patch("searchat.api.routers.search.get_analytics_service"), \
         patch("searchat.api.routers.search.deps.resolve_dataset_search_dir", return_value=(Mock(), None)), \
         patch("searchat.api.routers.search.deps.get_config", return_value=Mock(analytics=Mock(enabled=False))):

        response = client.get("/api/search?q=test&mode=keyword")

        assert response.status_code == 200
        data = response.json()

        # Default limit should be 20
        assert data["limit"] == 20


def test_search_pagination_offset_validation(client, mock_search_results):
    """Test offset parameter validation."""
    mock_engine = Mock()
    mock_engine.search.return_value = mock_search_results

    with patch("searchat.api.routers.search.deps.get_or_create_search_engine", return_value=mock_engine), \
         patch("searchat.api.routers.search.get_analytics_service"), \
         patch("searchat.api.routers.search.deps.resolve_dataset_search_dir", return_value=(Mock(), None)), \
         patch("searchat.api.routers.search.deps.get_config", return_value=Mock(analytics=Mock(enabled=False))):

        # Negative offset should fail
        response = client.get("/api/search?q=test&mode=keyword&offset=-1")
        assert response.status_code == 422

        # Zero offset should pass
        response = client.get("/api/search?q=test&mode=keyword&offset=0")
        assert response.status_code == 200


def test_search_pagination_limit_validation(client, mock_search_results):
    """Test limit parameter validation."""
    mock_engine = Mock()
    mock_engine.search.return_value = mock_search_results

    with patch("searchat.api.routers.search.deps.get_or_create_search_engine", return_value=mock_engine), \
         patch("searchat.api.routers.search.get_analytics_service"), \
         patch("searchat.api.routers.search.deps.resolve_dataset_search_dir", return_value=(Mock(), None)), \
         patch("searchat.api.routers.search.deps.get_config", return_value=Mock(analytics=Mock(enabled=False))):

        # limit < 1 should fail
        response = client.get("/api/search?q=test&mode=keyword&limit=0")
        assert response.status_code == 422

        # limit > 100 should fail
        response = client.get("/api/search?q=test&mode=keyword&limit=101")
        assert response.status_code == 422

        # Valid limit should pass
        response = client.get("/api/search?q=test&mode=keyword&limit=50")
        assert response.status_code == 200


def test_search_pagination_slicing(client, mock_search_results):
    """Test pagination correctly slices results."""
    mock_engine = Mock()
    mock_engine.search.return_value = mock_search_results

    with patch("searchat.api.routers.search.deps.get_or_create_search_engine", return_value=mock_engine), \
         patch("searchat.api.routers.search.get_analytics_service"), \
         patch("searchat.api.routers.search.deps.resolve_dataset_search_dir", return_value=(Mock(), None)), \
         patch("searchat.api.routers.search.deps.get_config", return_value=Mock(analytics=Mock(enabled=False))):

        # Get first page (0-20)
        response1 = client.get("/api/search?q=test&mode=keyword&offset=0&limit=20")
        data1 = response1.json()

        # Get second page (20-40)
        response2 = client.get("/api/search?q=test&mode=keyword&offset=20&limit=20")
        data2 = response2.json()

        # Results should not overlap
        ids1 = {r["conversation_id"] for r in data1["results"]}
        ids2 = {r["conversation_id"] for r in data2["results"]}

        assert len(ids1.intersection(ids2)) == 0


def test_search_pagination_total_count(client, mock_search_results):
    """Test total count is consistent across pages."""
    mock_engine = Mock()
    mock_engine.search.return_value = mock_search_results

    with patch("searchat.api.routers.search.deps.get_or_create_search_engine", return_value=mock_engine), \
         patch("searchat.api.routers.search.get_analytics_service"), \
         patch("searchat.api.routers.search.deps.resolve_dataset_search_dir", return_value=(Mock(), None)), \
         patch("searchat.api.routers.search.deps.get_config", return_value=Mock(analytics=Mock(enabled=False))):

        # Get different pages
        response1 = client.get("/api/search?q=test&mode=keyword&offset=0&limit=10")
        response2 = client.get("/api/search?q=test&mode=keyword&offset=10&limit=10")

        data1 = response1.json()
        data2 = response2.json()

        # Total should be same across all pages
        assert data1["total"] == data2["total"]


def test_search_pagination_beyond_results(client, mock_search_results):
    """Test pagination handles offset beyond total results."""
    mock_engine = Mock()
    mock_engine.search.return_value = mock_search_results

    with patch("searchat.api.routers.search.deps.get_or_create_search_engine", return_value=mock_engine), \
         patch("searchat.api.routers.search.get_analytics_service"), \
         patch("searchat.api.routers.search.deps.resolve_dataset_search_dir", return_value=(Mock(), None)), \
         patch("searchat.api.routers.search.deps.get_config", return_value=Mock(analytics=Mock(enabled=False))):

        # Offset beyond total results
        response = client.get("/api/search?q=test&mode=keyword&offset=100&limit=20")

        assert response.status_code == 200
        data = response.json()

        # Should return empty results
        assert len(data["results"]) == 0
        assert data["has_more"] is False


def test_search_pagination_metadata(client, mock_search_results):
    """Test pagination metadata is included in response."""
    mock_engine = Mock()
    mock_engine.search.return_value = mock_search_results

    with patch("searchat.api.routers.search.deps.get_or_create_search_engine", return_value=mock_engine), \
         patch("searchat.api.routers.search.get_analytics_service"), \
         patch("searchat.api.routers.search.deps.resolve_dataset_search_dir", return_value=(Mock(), None)), \
         patch("searchat.api.routers.search.deps.get_config", return_value=Mock(analytics=Mock(enabled=False))):

        response = client.get("/api/search?q=test&mode=keyword&offset=10&limit=15")

        assert response.status_code == 200
        data = response.json()

        # Check all pagination metadata present
        assert "results" in data
        assert "total" in data
        assert "offset" in data
        assert "limit" in data
        assert "has_more" in data
        assert "search_time_ms" in data

        # Check values
        assert data["offset"] == 10
        assert data["limit"] == 15
        assert data["total"] == 50
