"""API tests for conversation similarity endpoint."""
from __future__ import annotations

import pytest
import numpy as np
from unittest.mock import Mock, patch, MagicMock
from fastapi.testclient import TestClient

from searchat.api.app import app


@pytest.fixture
def client():
    """FastAPI test client."""
    return TestClient(app)


@pytest.fixture
def mock_duckdb_store():
    """Mock DuckDBStore."""
    mock = Mock()

    # Mock get_conversation_meta
    def _get_conversation_meta(conversation_id):
        if conversation_id == "conv-123":
            return {
                'conversation_id': "conv-123",
                'title': "Python Testing Tutorial",
                'project_id': "project-a"
            }
        return None

    mock.get_conversation_meta.side_effect = _get_conversation_meta

    # Mock _connect for DuckDB queries
    mock_conn = Mock()

    # Mock chunk text query result
    mock_conn.execute.return_value.fetchone.return_value = (
        "This is a tutorial about Python testing frameworks like pytest.",
    )

    # Mock similar conversations query result
    mock_conn.execute.return_value.fetchall.return_value = [
        (
            "conv-456",  # conversation_id
            "project-a",  # project_id
            "Advanced Python Testing",  # title
            "2026-01-20T10:00:00",  # created_at
            "2026-01-28T10:00:00",  # updated_at
            15,  # message_count
            "/path/to/conv-456.jsonl",  # file_path
            0.15  # distance
        ),
        (
            "conv-789",  # conversation_id
            "project-b",  # project_id
            "Unit Testing Best Practices",  # title
            "2026-01-15T10:00:00",  # created_at
            "2026-01-25T10:00:00",  # updated_at
            20,  # message_count
            "/path/to/conv-789.jsonl",  # file_path
            0.25  # distance
        )
    ]

    mock._connect.return_value = mock_conn

    return mock


@pytest.fixture
def mock_search_engine():
    """Mock SearchEngine."""
    mock = Mock()

    # Mock FAISS index
    mock_faiss = Mock()

    # Mock FAISS search results
    # Returns distances and labels (vector IDs)
    mock_faiss.search.return_value = (
        np.array([[0.15, 0.25, 0.35, 0.45]]),  # distances
        np.array([[100, 200, 300, 400]])  # vector IDs
    )

    mock.faiss_index = mock_faiss
    mock.metadata_path = "/path/to/metadata.parquet"
    mock.conversations_glob = "/path/to/conversations/*.parquet"

    # Mock embedder
    mock_embedder = Mock()
    mock_embedder.encode.return_value = np.array([0.1, 0.2, 0.3])  # Mock embedding
    mock.embedder = mock_embedder

    # Mock ensure methods
    mock.ensure_faiss_loaded = Mock()
    mock.ensure_embedder_loaded = Mock()

    return mock


def test_get_similar_conversations(client, mock_duckdb_store, mock_search_engine):
    """Test GET /api/conversation/{id}/similar returns similar conversations."""
    with patch("searchat.api.routers.conversations.deps.get_duckdb_store", return_value=mock_duckdb_store), \
         patch("searchat.api.routers.conversations.deps.get_search_engine", return_value=mock_search_engine):

        response = client.get("/api/conversation/conv-123/similar")

        assert response.status_code == 200
        data = response.json()

        assert data["conversation_id"] == "conv-123"
        assert "similar_conversations" in data
        assert len(data["similar_conversations"]) == 2

        # Check first similar conversation
        sim1 = data["similar_conversations"][0]
        assert sim1["conversation_id"] == "conv-456"
        assert sim1["title"] == "Advanced Python Testing"
        assert sim1["project_id"] == "project-a"
        assert sim1["message_count"] == 15
        assert 0.0 <= sim1["similarity_score"] <= 1.0

        # Check second similar conversation
        sim2 = data["similar_conversations"][1]
        assert sim2["conversation_id"] == "conv-789"
        assert 0.0 <= sim2["similarity_score"] <= 1.0

        # Verify FAISS was loaded
        mock_search_engine.ensure_faiss_loaded.assert_called_once()
        mock_search_engine.ensure_embedder_loaded.assert_called_once()


def test_get_similar_conversations_with_limit(client, mock_duckdb_store, mock_search_engine):
    """Test similarity endpoint respects limit parameter."""
    with patch("searchat.api.routers.conversations.deps.get_duckdb_store", return_value=mock_duckdb_store), \
         patch("searchat.api.routers.conversations.deps.get_search_engine", return_value=mock_search_engine):

        response = client.get("/api/conversation/conv-123/similar?limit=10")

        assert response.status_code == 200

        # Verify embedder was called
        mock_search_engine.embedder.encode.assert_called_once()


def test_get_similar_conversations_limit_validation(client, mock_duckdb_store, mock_search_engine):
    """Test limit parameter validation."""
    with patch("searchat.api.routers.conversations.deps.get_duckdb_store", return_value=mock_duckdb_store), \
         patch("searchat.api.routers.conversations.deps.get_search_engine", return_value=mock_search_engine):

        # limit < 1 should fail
        response = client.get("/api/conversation/conv-123/similar?limit=0")
        assert response.status_code == 422

        # limit > 20 should fail
        response = client.get("/api/conversation/conv-123/similar?limit=21")
        assert response.status_code == 422

        # Valid limit should pass
        response = client.get("/api/conversation/conv-123/similar?limit=10")
        assert response.status_code == 200


def test_get_similar_conversations_nonexistent(client, mock_duckdb_store, mock_search_engine):
    """Test similarity for nonexistent conversation returns 404."""
    with patch("searchat.api.routers.conversations.deps.get_duckdb_store", return_value=mock_duckdb_store), \
         patch("searchat.api.routers.conversations.deps.get_search_engine", return_value=mock_search_engine):

        response = client.get("/api/conversation/nonexistent/similar")

        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()


def test_get_similar_conversations_no_faiss_index(client, mock_duckdb_store):
    """Test similarity endpoint handles missing FAISS index."""
    mock_engine = Mock()
    mock_engine.faiss_index = None  # No index available
    mock_engine.ensure_faiss_loaded = Mock()
    mock_engine.ensure_embedder_loaded = Mock()

    mock_duckdb_store.get_conversation_meta.return_value = {
        'conversation_id': "conv-123",
        'title': "Test",
        'project_id': "project"
    }

    with patch("searchat.api.routers.conversations.deps.get_duckdb_store", return_value=mock_duckdb_store), \
         patch("searchat.api.routers.conversations.deps.get_search_engine", return_value=mock_engine):

        response = client.get("/api/conversation/conv-123/similar")

        assert response.status_code == 503
        assert "FAISS index not available" in response.json()["detail"]


def test_get_similar_conversations_no_embedder(client, mock_duckdb_store, mock_search_engine):
    """Test similarity endpoint handles missing embedder."""
    mock_search_engine.embedder = None  # No embedder available

    with patch("searchat.api.routers.conversations.deps.get_duckdb_store", return_value=mock_duckdb_store), \
         patch("searchat.api.routers.conversations.deps.get_search_engine", return_value=mock_search_engine):

        response = client.get("/api/conversation/conv-123/similar")

        assert response.status_code == 503
        assert "Embedder not available" in response.json()["detail"]


def test_get_similar_conversations_no_embeddings(client, mock_duckdb_store, mock_search_engine):
    """Test similarity endpoint handles conversations without embeddings."""
    # Mock DuckDB to return no chunk text
    mock_conn = Mock()
    mock_conn.execute.return_value.fetchone.return_value = None
    mock_duckdb_store._connect.return_value = mock_conn

    with patch("searchat.api.routers.conversations.deps.get_duckdb_store", return_value=mock_duckdb_store), \
         patch("searchat.api.routers.conversations.deps.get_search_engine", return_value=mock_search_engine):

        response = client.get("/api/conversation/conv-123/similar")

        assert response.status_code == 404
        assert "No embeddings found" in response.json()["detail"]


def test_get_similar_conversations_empty_results(client, mock_duckdb_store, mock_search_engine):
    """Test similarity endpoint handles no similar conversations found."""
    # Mock DuckDB to return empty results
    mock_conn = Mock()
    mock_conn.execute.return_value.fetchone.return_value = ("chunk text",)
    mock_conn.execute.return_value.fetchall.return_value = []
    mock_duckdb_store._connect.return_value = mock_conn

    # Mock FAISS to return no valid results
    mock_search_engine.faiss_index.search.return_value = (
        np.array([[]]),
        np.array([[]])
    )

    with patch("searchat.api.routers.conversations.deps.get_duckdb_store", return_value=mock_duckdb_store), \
         patch("searchat.api.routers.conversations.deps.get_search_engine", return_value=mock_search_engine):

        response = client.get("/api/conversation/conv-123/similar")

        assert response.status_code == 200
        data = response.json()
        assert data["similar_conversations"] == []


def test_similarity_score_calculation(client, mock_duckdb_store, mock_search_engine):
    """Test similarity score is correctly calculated from distance."""
    with patch("searchat.api.routers.conversations.deps.get_duckdb_store", return_value=mock_duckdb_store), \
         patch("searchat.api.routers.conversations.deps.get_search_engine", return_value=mock_search_engine):

        response = client.get("/api/conversation/conv-123/similar")

        assert response.status_code == 200
        data = response.json()

        # Similarity score should be 1.0 / (1.0 + distance)
        # First result has distance 0.15, score should be 1.0 / 1.15 ≈ 0.87
        assert 0.86 < data["similar_conversations"][0]["similarity_score"] < 0.88


def test_similar_conversations_sorted_by_similarity(client, mock_duckdb_store, mock_search_engine):
    """Test similar conversations are sorted by similarity score (descending)."""
    with patch("searchat.api.routers.conversations.deps.get_duckdb_store", return_value=mock_duckdb_store), \
         patch("searchat.api.routers.conversations.deps.get_search_engine", return_value=mock_search_engine):

        response = client.get("/api/conversation/conv-123/similar")

        assert response.status_code == 200
        data = response.json()

        # Results should be sorted by similarity score (higher first)
        scores = [conv["similarity_score"] for conv in data["similar_conversations"]]
        assert scores == sorted(scores, reverse=True)


def test_similar_conversations_excludes_source(client, mock_duckdb_store, mock_search_engine):
    """Test source conversation is excluded from similar results."""
    # This is tested indirectly via the SQL query in the endpoint
    # The WHERE clause filters out m.conversation_id != ?

    with patch("searchat.api.routers.conversations.deps.get_duckdb_store", return_value=mock_duckdb_store), \
         patch("searchat.api.routers.conversations.deps.get_search_engine", return_value=mock_search_engine):

        response = client.get("/api/conversation/conv-123/similar")

        assert response.status_code == 200
        data = response.json()

        # Source conversation should not be in results
        conv_ids = [conv["conversation_id"] for conv in data["similar_conversations"]]
        assert "conv-123" not in conv_ids


def test_similar_conversations_tool_detection(client, mock_duckdb_store, mock_search_engine):
    """Test tool is correctly detected from file path."""
    with patch("searchat.api.routers.conversations.deps.get_duckdb_store", return_value=mock_duckdb_store), \
         patch("searchat.api.routers.conversations.deps.get_search_engine", return_value=mock_search_engine):

        response = client.get("/api/conversation/conv-123/similar")

        assert response.status_code == 200
        data = response.json()

        # Conversations ending with .jsonl should be detected as "claude"
        assert data["similar_conversations"][0]["tool"] == "claude"


def test_similar_conversations_includes_metadata(client, mock_duckdb_store, mock_search_engine):
    """Test similar conversations include all required metadata."""
    with patch("searchat.api.routers.conversations.deps.get_duckdb_store", return_value=mock_duckdb_store), \
         patch("searchat.api.routers.conversations.deps.get_search_engine", return_value=mock_search_engine):

        response = client.get("/api/conversation/conv-123/similar")

        assert response.status_code == 200
        data = response.json()

        conv = data["similar_conversations"][0]
        assert "conversation_id" in conv
        assert "title" in conv
        assert "project_id" in conv
        assert "message_count" in conv
        assert "similarity_score" in conv
        assert "tool" in conv
        assert "created_at" in conv
        assert "updated_at" in conv
