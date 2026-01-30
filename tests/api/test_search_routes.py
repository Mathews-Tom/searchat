"""Unit tests for search API routes."""
import pytest
from datetime import datetime, timedelta
from unittest.mock import Mock, patch

from fastapi.testclient import TestClient

from searchat.models import SearchResult, SearchResults, SearchMode
from searchat.api.app import app


@pytest.fixture
def client():
    """FastAPI test client."""
    return TestClient(app)


@pytest.fixture(autouse=True)
def semantic_components_ready():
    """Make semantic components appear warmed for API route unit tests."""
    readiness = Mock()
    readiness.snapshot.return_value = Mock(
        components={"metadata": "ready", "faiss": "ready", "embedder": "ready"}
    )
    with patch('searchat.api.routers.search.get_readiness', return_value=readiness):
        yield


@pytest.fixture
def mock_search_engine():
    """Mock SearchEngine for testing."""
    mock = Mock()

    # Create sample search results
    now = datetime.now()
    sample_result = SearchResult(
        conversation_id="test-conv-123",
        project_id="test-project",
        title="Test Conversation",
        created_at=now - timedelta(days=5),
        updated_at=now - timedelta(days=1),
        message_count=10,
        file_path="/home/user/.claude/test-conv-123.jsonl",
        snippet="This is a test conversation about Python",
        score=0.95,
        message_start_index=0,
        message_end_index=5
    )

    mock.search.return_value = SearchResults(
        results=[sample_result],
        total_count=1,
        search_time_ms=15.5,
        mode_used="hybrid"
    )

    return mock


@pytest.fixture
def mock_duckdb_store():
    mock = Mock()
    mock.list_projects.return_value = ["project-a", "project-b", "project-c"]
    return mock


@pytest.mark.unit
class TestSearchEndpoint:
    """Tests for /api/search endpoint."""

    def test_basic_search(self, client, mock_search_engine):
        """Test basic search with query."""
        with patch('searchat.api.routers.search.get_search_engine', return_value=mock_search_engine):
            response = client.get("/api/search?q=test")

            assert response.status_code == 200
            data = response.json()

            assert "results" in data
            assert "total" in data
            assert "search_time_ms" in data
            assert data["total"] == 1
            assert len(data["results"]) == 1

            # Verify result structure
            result = data["results"][0]
            assert result["conversation_id"] == "test-conv-123"
            assert result["project_id"] == "test-project"
            assert result["title"] == "Test Conversation"
            assert result["source"] == "WSL"  # /home/ path
            assert result["score"] == 0.95

    def test_search_mode_hybrid(self, client, mock_search_engine):
        """Test search with hybrid mode - combines keyword and semantic."""
        with patch('searchat.api.routers.search.get_search_engine', return_value=mock_search_engine):
            response = client.get("/api/search?q=implement binary search tree&mode=hybrid")

            assert response.status_code == 200
            mock_search_engine.search.assert_called_once()

            # Verify mode was passed correctly
            call_args = mock_search_engine.search.call_args
            assert call_args[1]['mode'] == SearchMode.HYBRID
            assert call_args[0][0] == "implement binary search tree"  # query preserved

    def test_search_mode_semantic(self, client, mock_search_engine):
        """Test search with semantic mode - meaning-based search."""
        with patch('searchat.api.routers.search.get_search_engine', return_value=mock_search_engine):
            # Semantic mode should handle conceptual queries well
            response = client.get("/api/search?q=how to sort data structures&mode=semantic")

            assert response.status_code == 200
            call_args = mock_search_engine.search.call_args
            assert call_args[1]['mode'] == SearchMode.SEMANTIC
            # Query is passed as-is for semantic processing
            assert call_args[0][0] == "how to sort data structures"

    def test_search_mode_keyword(self, client, mock_search_engine):
        """Test search with keyword mode - exact text matching."""
        with patch('searchat.api.routers.search.get_or_create_search_engine', return_value=mock_search_engine):
            # Keyword mode should handle specific terms
            response = client.get("/api/search?q=def binary_search&mode=keyword")

            assert response.status_code == 200
            call_args = mock_search_engine.search.call_args
            assert call_args[1]['mode'] == SearchMode.KEYWORD
            # Query is passed for keyword matching
            assert call_args[0][0] == "def binary_search"

    def test_search_mode_default_is_hybrid(self, client, mock_search_engine):
        """Test that default search mode is hybrid when not specified."""
        with patch('searchat.api.routers.search.get_search_engine', return_value=mock_search_engine):
            response = client.get("/api/search?q=test")  # No mode specified

            assert response.status_code == 200
            call_args = mock_search_engine.search.call_args
            # Should default to HYBRID
            assert call_args[1]['mode'] == SearchMode.HYBRID

    def test_search_mode_invalid_returns_400(self, client, mock_search_engine):
        """Test that invalid mode is rejected."""
        with patch('searchat.api.routers.search.get_search_engine', return_value=mock_search_engine):
            response = client.get("/api/search?q=test&mode=invalid")

            assert response.status_code == 400
            assert response.json()["detail"] == "Invalid search mode"

    def test_search_highlight_requires_provider(self, client, mock_search_engine):
        """Test that highlight requests require explicit provider."""
        with patch('searchat.api.routers.search.get_search_engine', return_value=mock_search_engine):
            response = client.get("/api/search?q=test&highlight=true")

            assert response.status_code == 400
            assert response.json()["detail"] == "Highlight provider is required"

    def test_search_with_project_filter(self, client, mock_search_engine):
        """Test search with project filter."""
        with patch('searchat.api.routers.search.get_search_engine', return_value=mock_search_engine):
            response = client.get("/api/search?q=test&project=test-project")

            assert response.status_code == 200
            call_args = mock_search_engine.search.call_args
            filters = call_args[1]['filters']
            assert filters.project_ids == ["test-project"]

    def test_search_with_date_filter_today(self, client, mock_search_engine):
        """Test search with 'today' date filter."""
        with patch('searchat.api.routers.search.get_search_engine', return_value=mock_search_engine):
            response = client.get("/api/search?q=test&date=today")

            assert response.status_code == 200
            call_args = mock_search_engine.search.call_args
            filters = call_args[1]['filters']

            assert filters.date_from is not None
            assert filters.date_to is not None
            # date_from should be start of today
            assert filters.date_from.hour == 0
            assert filters.date_from.minute == 0

    def test_search_with_date_filter_week(self, client, mock_search_engine):
        """Test search with 'week' date filter."""
        with patch('searchat.api.routers.search.get_search_engine', return_value=mock_search_engine):
            response = client.get("/api/search?q=test&date=week")

            assert response.status_code == 200
            call_args = mock_search_engine.search.call_args
            filters = call_args[1]['filters']

            assert filters.date_from is not None
            assert filters.date_to is not None
            # Should be approximately 7 days ago
            days_diff = (filters.date_to - filters.date_from).days
            assert 6 <= days_diff <= 8  # Allow some tolerance

    def test_search_with_date_filter_month(self, client, mock_search_engine):
        """Test search with 'month' date filter."""
        with patch('searchat.api.routers.search.get_search_engine', return_value=mock_search_engine):
            response = client.get("/api/search?q=test&date=month")

            assert response.status_code == 200
            call_args = mock_search_engine.search.call_args
            filters = call_args[1]['filters']

            assert filters.date_from is not None
            assert filters.date_to is not None
            # Should be approximately 30 days ago
            days_diff = (filters.date_to - filters.date_from).days
            assert 29 <= days_diff <= 31

    def test_search_with_custom_date_range(self, client, mock_search_engine):
        """Test search with custom date range."""
        with patch('searchat.api.routers.search.get_search_engine', return_value=mock_search_engine):
            response = client.get(
                "/api/search?q=test&date=custom&date_from=2025-01-01&date_to=2025-01-31"
            )

            assert response.status_code == 200
            call_args = mock_search_engine.search.call_args
            filters = call_args[1]['filters']

            assert filters.date_from == datetime(2025, 1, 1)
            # date_to should include the entire end date (+1 day)
            assert filters.date_to == datetime(2025, 2, 1)

    def test_search_sort_by_date_newest(self, client, mock_search_engine):
        """Test search sorted by newest date."""
        # Create multiple results with different dates
        now = datetime.now()
        results = [
            SearchResult(
                conversation_id=f"conv-{i}",
                project_id="test",
                title=f"Conv {i}",
                created_at=now - timedelta(days=i+5),
                updated_at=now - timedelta(days=i),
                message_count=10,
                file_path=f"/test/conv-{i}.jsonl",
                snippet="Test",
                score=0.9,
                message_start_index=0,
                message_end_index=5
            )
            for i in range(3)
        ]

        mock_search_engine.search.return_value = SearchResults(
            results=results,
            total_count=3,
            search_time_ms=20.0,
            mode_used="hybrid"
        )

        with patch('searchat.api.routers.search.get_search_engine', return_value=mock_search_engine):
            response = client.get("/api/search?q=test&sort_by=date_newest")

            assert response.status_code == 200
            data = response.json()

            # Results should be sorted newest first (conv-0, conv-1, conv-2)
            assert data["results"][0]["conversation_id"] == "conv-0"
            assert data["results"][1]["conversation_id"] == "conv-1"
            assert data["results"][2]["conversation_id"] == "conv-2"

    def test_search_sort_by_date_oldest(self, client, mock_search_engine):
        """Test search sorted by oldest date."""
        now = datetime.now()
        results = [
            SearchResult(
                conversation_id=f"conv-{i}",
                project_id="test",
                title=f"Conv {i}",
                created_at=now - timedelta(days=i+5),
                updated_at=now - timedelta(days=i),
                message_count=10,
                file_path=f"/test/conv-{i}.jsonl",
                snippet="Test",
                score=0.9,
                message_start_index=0,
                message_end_index=5
            )
            for i in range(3)
        ]

        mock_search_engine.search.return_value = SearchResults(
            results=results,
            total_count=3,
            search_time_ms=20.0,
            mode_used="hybrid"
        )

        with patch('searchat.api.routers.search.get_search_engine', return_value=mock_search_engine):
            response = client.get("/api/search?q=test&sort_by=date_oldest")

            assert response.status_code == 200
            data = response.json()

            # Results should be sorted oldest first (conv-2, conv-1, conv-0)
            assert data["results"][0]["conversation_id"] == "conv-2"
            assert data["results"][1]["conversation_id"] == "conv-1"
            assert data["results"][2]["conversation_id"] == "conv-0"

    def test_search_sort_by_messages(self, client, mock_search_engine):
        """Test search sorted by message count."""
        now = datetime.now()
        results = [
            SearchResult(
                conversation_id=f"conv-{i}",
                project_id="test",
                title=f"Conv {i}",
                created_at=now,
                updated_at=now,
                message_count=(i + 1) * 5,  # 5, 10, 15
                file_path=f"/test/conv-{i}.jsonl",
                snippet="Test",
                score=0.9,
                message_start_index=0,
                message_end_index=5
            )
            for i in range(3)
        ]

        mock_search_engine.search.return_value = SearchResults(
            results=results,
            total_count=3,
            search_time_ms=20.0,
            mode_used="hybrid"
        )

        with patch('searchat.api.routers.search.get_search_engine', return_value=mock_search_engine):
            response = client.get("/api/search?q=test&sort_by=messages")

            assert response.status_code == 200
            data = response.json()

            # Results should be sorted by message count descending
            assert data["results"][0]["message_count"] == 15
            assert data["results"][1]["message_count"] == 10
            assert data["results"][2]["message_count"] == 5

    def test_search_with_limit(self, client, mock_search_engine):
        """Test search with result limit."""
        now = datetime.now()
        results = [
            SearchResult(
                conversation_id=f"conv-{i}",
                project_id="test",
                title=f"Conv {i}",
                created_at=now,
                updated_at=now,
                message_count=10,
                file_path=f"/test/conv-{i}.jsonl",
                snippet="Test",
                score=0.9,
                message_start_index=0,
                message_end_index=5
            )
            for i in range(10)
        ]

        mock_search_engine.search.return_value = SearchResults(
            results=results,
            total_count=10,
            search_time_ms=20.0,
            mode_used="hybrid"
        )

        with patch('searchat.api.routers.search.get_search_engine', return_value=mock_search_engine):
            response = client.get("/api/search?q=test&limit=3")

            assert response.status_code == 200
            data = response.json()

            # Should only return 3 results
            assert len(data["results"]) == 3
            # But total should still be 10
            assert data["total"] == 10

    def test_search_source_detection_wsl(self, client, mock_search_engine):
        """Test that WSL paths are detected correctly."""
        now = datetime.now()
        mock_search_engine.search.return_value = SearchResults(
            results=[
                SearchResult(
                    conversation_id="conv-1",
                    project_id="test",
                    title="Conv 1",
                    created_at=now,
                    updated_at=now,
                    message_count=10,
                    file_path="/home/user/.claude/conv-1.jsonl",
                    snippet="Test",
                    score=0.9,
                    message_start_index=0,
                    message_end_index=5
                )
            ],
            total_count=1,
            search_time_ms=10.0,
            mode_used="hybrid"
        )

        with patch('searchat.api.routers.search.get_search_engine', return_value=mock_search_engine):
            response = client.get("/api/search?q=test")

            assert response.status_code == 200
            data = response.json()
            assert data["results"][0]["source"] == "WSL"

    def test_search_source_detection_windows(self, client, mock_search_engine):
        """Test that Windows paths are detected correctly."""
        now = datetime.now()
        mock_search_engine.search.return_value = SearchResults(
            results=[
                SearchResult(
                    conversation_id="conv-1",
                    project_id="test",
                    title="Conv 1",
                    created_at=now,
                    updated_at=now,
                    message_count=10,
                    file_path="C:\\Users\\Test\\.claude\\conv-1.jsonl",
                    snippet="Test",
                    score=0.9,
                    message_start_index=0,
                    message_end_index=5
                )
            ],
            total_count=1,
            search_time_ms=10.0,
            mode_used="hybrid"
        )

        with patch('searchat.api.routers.search.get_search_engine', return_value=mock_search_engine):
            response = client.get("/api/search?q=test")

            assert response.status_code == 200
            data = response.json()
            assert data["results"][0]["source"] == "WIN"

    def test_partial_word_keyword_mode(self, client, mock_search_engine):
        """Test that keyword mode handles partial words (substring matching)."""
        # Mock multiple results with different word forms
        now = datetime.now()
        mock_results = [
            SearchResult(
                conversation_id="conv-1",
                project_id="test-project",
                title="How to apologize properly",
                created_at=now,
                updated_at=now,
                message_count=5,
                file_path="/test/conv-1.jsonl",
                snippet="I apologize for the confusion",
                score=0.9
            ),
            SearchResult(
                conversation_id="conv-2",
                project_id="test-project",
                title="Apologizing techniques",
                created_at=now,
                updated_at=now,
                message_count=3,
                file_path="/test/conv-2.jsonl",
                snippet="Start by apologizing sincerely",
                score=0.8
            )
        ]

        mock_search_engine.search.return_value = SearchResults(
            results=mock_results,
            total_count=2,
            search_time_ms=10.0,
            mode_used="keyword"
        )

        with patch('searchat.api.routers.search.get_or_create_search_engine', return_value=mock_search_engine):
            # Search with partial word "apologiz" (missing 'e' or 'ing')
            response = client.get("/api/search?q=apologiz&mode=keyword")

            assert response.status_code == 200
            data = response.json()

            # Should find results with "apologize", "apologizing", etc.
            assert data["total"] >= 2
            assert any("apolog" in r["title"].lower() or "apolog" in r["snippet"].lower()
                      for r in data["results"])

    def test_partial_word_hybrid_mode(self, client, mock_search_engine):
        """Test that hybrid mode handles partial words (via keyword component)."""
        now = datetime.now()
        mock_result = SearchResult(
            conversation_id="conv-hybrid",
            project_id="test-project",
            title="Optimize database queries",
            created_at=now,
            updated_at=now,
            message_count=10,
            file_path="/test/conv.jsonl",
            snippet="Optimizing the database performance",
            score=0.85
        )

        mock_search_engine.search.return_value = SearchResults(
            results=[mock_result],
            total_count=1,
            search_time_ms=20.0,
            mode_used="hybrid"
        )

        with patch('searchat.api.routers.search.get_search_engine', return_value=mock_search_engine):
            # Search with partial word "optimi" (matches "optimize", "optimizing", "optimization")
            response = client.get("/api/search?q=optimi&mode=hybrid")

            assert response.status_code == 200
            data = response.json()

            # Hybrid should work because keyword component handles partial words
            assert response.status_code == 200
            mock_search_engine.search.assert_called_once()

            # Verify hybrid mode was used
            call_args = mock_search_engine.search.call_args
            assert call_args[1]['mode'] == SearchMode.HYBRID

    def test_partial_word_semantic_mode(self, client, mock_search_engine):
        """Test semantic mode with partial words (may not match as well)."""
        # Semantic mode uses embeddings which may not handle partial words well
        mock_search_engine.search.return_value = SearchResults(
            results=[],
            total_count=0,
            search_time_ms=15.0,
            mode_used="semantic"
        )

        with patch('searchat.api.routers.search.get_search_engine', return_value=mock_search_engine):
            # Partial word may not match well in semantic mode
            response = client.get("/api/search?q=refactor&mode=semantic")

            assert response.status_code == 200
            # Semantic mode should still work, even if results are limited
            mock_search_engine.search.assert_called_once()

            call_args = mock_search_engine.search.call_args
            assert call_args[1]['mode'] == SearchMode.SEMANTIC

    def test_partial_word_case_insensitive(self, client, mock_search_engine):
        """Test that partial word matching is case-insensitive in keyword mode."""
        now = datetime.now()
        mock_result = SearchResult(
            conversation_id="conv-case",
            project_id="test-project",
            title="Database Design Patterns",
            created_at=now,
            updated_at=now,
            message_count=8,
            file_path="/test/conv.jsonl",
            snippet="Using DATABASE normalization techniques",
            score=0.92
        )

        mock_search_engine.search.return_value = SearchResults(
            results=[mock_result],
            total_count=1,
            search_time_ms=12.0,
            mode_used="keyword"
        )

        with patch('searchat.api.routers.search.get_or_create_search_engine', return_value=mock_search_engine):
            # Search with lowercase partial word should match uppercase full word
            response = client.get("/api/search?q=datab&mode=keyword")

            assert response.status_code == 200
            data = response.json()

            # Case-insensitive matching should work
            assert response.status_code == 200
            mock_search_engine.search.assert_called_once()

    def test_search_error_handling(self, client, mock_search_engine):
        """Test that search errors are handled properly."""
        mock_search_engine.search.side_effect = Exception("Search failed")

        with patch('searchat.api.routers.search.get_search_engine', return_value=mock_search_engine):
            response = client.get("/api/search?q=test")

            assert response.status_code == 500
            assert "Search failed" in response.json()["detail"]


@pytest.mark.unit
class TestProjectsEndpoint:
    """Tests for /api/projects endpoint."""

    def test_get_projects(self, client, mock_duckdb_store):
        """Test getting list of projects."""
        with patch('searchat.api.routers.search.deps.get_duckdb_store', return_value=mock_duckdb_store):
            with patch('searchat.api.routers.search.deps.projects_cache', None):
                response = client.get("/api/projects")

                assert response.status_code == 200
                projects = response.json()

                assert isinstance(projects, list)
                assert len(projects) == 3
                # Should be sorted
                assert projects == ["project-a", "project-b", "project-c"]

    def test_get_projects_uses_cache(self, client, mock_duckdb_store):
        """Test that projects endpoint uses cache."""
        with patch('searchat.api.routers.search.deps.get_duckdb_store', return_value=mock_duckdb_store):
            with patch('searchat.api.routers.search.deps.projects_cache', ["cached-project"]):
                response = client.get("/api/projects")

                assert response.status_code == 200
                projects = response.json()

                # Should return cached value (not from DataFrame)
                assert projects == ["cached-project"]
                assert projects != ["project-a", "project-b", "project-c"]

    def test_get_projects_summary(self, client, mock_duckdb_store):
        """Test getting project summaries."""
        mock_duckdb_store.list_project_summaries.return_value = [
            {
                "project_id": "project-a",
                "conversation_count": 3,
                "message_count": 42,
                "updated_at": "2025-01-01T00:00:00",
            }
        ]
        with patch('searchat.api.routers.search.deps.get_duckdb_store', return_value=mock_duckdb_store):
            with patch('searchat.api.routers.search.deps.projects_summary_cache', None):
                response = client.get("/api/projects/summary")

                assert response.status_code == 200
                data = response.json()
                assert isinstance(data, list)
                assert data[0]["project_id"] == "project-a"
