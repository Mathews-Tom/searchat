"""API tests for bookmarks routes."""
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
def mock_bookmarks_service():
    """Mock BookmarksService."""
    mock = Mock()

    mock._bookmarks = {}

    def _add_bookmark(conversation_id, notes=""):
        bookmark = {
            "conversation_id": conversation_id,
            "added_at": datetime.now().isoformat(),
            "notes": notes
        }
        mock._bookmarks[conversation_id] = bookmark
        return bookmark

    def _remove_bookmark(conversation_id):
        if conversation_id in mock._bookmarks:
            del mock._bookmarks[conversation_id]
            return True
        return False

    def _list_bookmarks():
        return list(mock._bookmarks.values())

    def _update_notes(conversation_id, notes):
        if conversation_id in mock._bookmarks:
            mock._bookmarks[conversation_id]["notes"] = notes
            return True
        return False

    def _is_bookmarked(conversation_id):
        return conversation_id in mock._bookmarks

    mock.add_bookmark.side_effect = _add_bookmark
    mock.remove_bookmark.side_effect = _remove_bookmark
    mock.list_bookmarks.side_effect = _list_bookmarks
    mock.update_notes.side_effect = _update_notes
    mock.is_bookmarked.side_effect = _is_bookmarked

    return mock


@pytest.fixture
def mock_duckdb_store():
    """Mock DuckDBStore for conversation metadata."""
    mock = Mock()

    now = datetime.now()
    mock._conversations = {
        "conv-1": {
            "conversation_id": "conv-1",
            "project_id": "project-a",
            "title": "Test Conversation 1",
            "created_at": now,
            "updated_at": now,
            "message_count": 10,
            "file_path": "/path/to/conv-1.jsonl"
        },
        "conv-2": {
            "conversation_id": "conv-2",
            "project_id": "project-b",
            "title": "Test Conversation 2",
            "created_at": now,
            "updated_at": now,
            "message_count": 5,
            "file_path": "/path/to/conv-2.jsonl"
        }
    }

    def _get_conversation_meta(conversation_id):
        return mock._conversations.get(conversation_id)

    mock.get_conversation_meta.side_effect = _get_conversation_meta

    return mock


def test_get_bookmarks_empty(client, mock_bookmarks_service, mock_duckdb_store):
    """Test GET /api/bookmarks with no bookmarks."""
    with patch("searchat.api.routers.bookmarks.deps.get_bookmarks_service", return_value=mock_bookmarks_service), \
         patch("searchat.api.routers.bookmarks.deps.get_duckdb_store", return_value=mock_duckdb_store):

        response = client.get("/api/bookmarks")

        assert response.status_code == 200
        data = response.json()
        assert data["bookmarks"] == []


def test_add_bookmark(client, mock_bookmarks_service, mock_duckdb_store):
    """Test POST /api/bookmarks to add a bookmark."""
    with patch("searchat.api.routers.bookmarks.deps.get_bookmarks_service", return_value=mock_bookmarks_service), \
         patch("searchat.api.routers.bookmarks.deps.get_duckdb_store", return_value=mock_duckdb_store):

        response = client.post(
            "/api/bookmarks",
            json={"conversation_id": "conv-1", "notes": "Important"}
        )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["bookmark"]["conversation_id"] == "conv-1"
        assert data["bookmark"]["notes"] == "Important"
        assert "added_at" in data["bookmark"]


def test_add_bookmark_without_notes(client, mock_bookmarks_service, mock_duckdb_store):
    """Test POST /api/bookmarks without notes field."""
    with patch("searchat.api.routers.bookmarks.deps.get_bookmarks_service", return_value=mock_bookmarks_service), \
         patch("searchat.api.routers.bookmarks.deps.get_duckdb_store", return_value=mock_duckdb_store):

        response = client.post(
            "/api/bookmarks",
            json={"conversation_id": "conv-1"}
        )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["bookmark"]["conversation_id"] == "conv-1"
        assert data["bookmark"]["notes"] == ""


def test_add_bookmark_returns_404_when_conversation_missing(client, mock_bookmarks_service, mock_duckdb_store):
    with patch("searchat.api.routers.bookmarks.deps.get_bookmarks_service", return_value=mock_bookmarks_service), \
         patch("searchat.api.routers.bookmarks.deps.get_duckdb_store", return_value=mock_duckdb_store):

        response = client.post(
            "/api/bookmarks",
            json={"conversation_id": "missing", "notes": "x"},
        )

    assert response.status_code == 404
    assert "not found" in response.json()["detail"].lower()


def test_remove_bookmark(client, mock_bookmarks_service, mock_duckdb_store):
    """Test DELETE /api/bookmarks/{conversation_id}."""
    # Add bookmark first
    mock_bookmarks_service.add_bookmark("conv-1", "Test")

    with patch("searchat.api.routers.bookmarks.deps.get_bookmarks_service", return_value=mock_bookmarks_service):

        response = client.delete("/api/bookmarks/conv-1")

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True


def test_remove_nonexistent_bookmark(client, mock_bookmarks_service):
    """Test DELETE for nonexistent bookmark returns 404."""
    with patch("searchat.api.routers.bookmarks.deps.get_bookmarks_service", return_value=mock_bookmarks_service):

        response = client.delete("/api/bookmarks/nonexistent")

        assert response.status_code == 404


def test_update_bookmark_notes(client, mock_bookmarks_service, mock_duckdb_store):
    """Test PATCH /api/bookmarks/{conversation_id}/notes."""
    # Add bookmark first
    mock_bookmarks_service.add_bookmark("conv-1", "Original")

    with patch("searchat.api.routers.bookmarks.deps.get_bookmarks_service", return_value=mock_bookmarks_service):

        response = client.patch(
            "/api/bookmarks/conv-1/notes",
            json={"notes": "Updated notes"}
        )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "message" in data


def test_update_notes_nonexistent_bookmark(client, mock_bookmarks_service):
    """Test PATCH for nonexistent bookmark returns 404."""
    with patch("searchat.api.routers.bookmarks.deps.get_bookmarks_service", return_value=mock_bookmarks_service):

        response = client.patch(
            "/api/bookmarks/nonexistent/notes",
            json={"notes": "Test"}
        )

        assert response.status_code == 404


def test_get_bookmark_endpoint_returns_status(client, mock_bookmarks_service):
    mock_bookmarks_service.get_bookmark.side_effect = lambda cid: {"conversation_id": cid} if cid == "conv-1" else None
    with patch("searchat.api.routers.bookmarks.deps.get_bookmarks_service", return_value=mock_bookmarks_service):
        resp1 = client.get("/api/bookmarks/conv-1")
        resp2 = client.get("/api/bookmarks/conv-2")

    assert resp1.status_code == 200
    assert resp1.json()["is_bookmarked"] is True
    assert resp2.status_code == 200
    assert resp2.json()["is_bookmarked"] is False


def test_get_bookmarks_returns_500_on_exception(client, mock_bookmarks_service, mock_duckdb_store):
    mock_bookmarks_service.add_bookmark("conv-1", "")
    mock_duckdb_store.get_conversation_meta.side_effect = RuntimeError("boom")

    with patch("searchat.api.routers.bookmarks.deps.get_bookmarks_service", return_value=mock_bookmarks_service), \
         patch("searchat.api.routers.bookmarks.deps.get_duckdb_store", return_value=mock_duckdb_store):

        resp = client.get("/api/bookmarks")

    assert resp.status_code == 500
    assert resp.json()["detail"] == "boom"


def test_get_bookmarks_with_metadata(client, mock_bookmarks_service, mock_duckdb_store):
    """Test GET /api/bookmarks enriches bookmarks with conversation metadata."""
    # Add bookmarks
    mock_bookmarks_service.add_bookmark("conv-1", "Note 1")
    mock_bookmarks_service.add_bookmark("conv-2", "Note 2")

    with patch("searchat.api.routers.bookmarks.deps.get_bookmarks_service", return_value=mock_bookmarks_service), \
         patch("searchat.api.routers.bookmarks.deps.get_duckdb_store", return_value=mock_duckdb_store):

        response = client.get("/api/bookmarks")

        assert response.status_code == 200
        data = response.json()
        bookmarks = data["bookmarks"]

        assert len(bookmarks) == 2

        # Check metadata enrichment
        bookmark1 = next(b for b in bookmarks if b["conversation_id"] == "conv-1")
        assert bookmark1["title"] == "Test Conversation 1"
        assert bookmark1["project_id"] == "project-a"
        assert bookmark1["message_count"] == 10


def test_get_bookmarks_missing_metadata(client, mock_bookmarks_service, mock_duckdb_store):
    """Test GET /api/bookmarks handles missing conversation metadata gracefully."""
    # Add bookmark for conversation that doesn't exist in store
    mock_bookmarks_service.add_bookmark("conv-missing", "Note")

    with patch("searchat.api.routers.bookmarks.deps.get_bookmarks_service", return_value=mock_bookmarks_service), \
         patch("searchat.api.routers.bookmarks.deps.get_duckdb_store", return_value=mock_duckdb_store):

        response = client.get("/api/bookmarks")

        assert response.status_code == 200
        data = response.json()
        bookmarks = data["bookmarks"]

        # Bookmark should be included even without metadata
        assert len(bookmarks) == 1
        assert bookmarks[0]["conversation_id"] == "conv-missing"
        assert "title" not in bookmarks[0] or bookmarks[0]["title"] is None


def test_bookmark_validation(client, mock_bookmarks_service):
    """Test request validation for bookmark endpoints."""
    with patch("searchat.api.routers.bookmarks.deps.get_bookmarks_service", return_value=mock_bookmarks_service):

        # Missing conversation_id in POST
        response = client.post("/api/bookmarks", json={})
        assert response.status_code == 422

        # Missing notes in PATCH
        response = client.patch("/api/bookmarks/conv-1/notes", json={})
        assert response.status_code == 422


def test_multiple_bookmarks_operations(client, mock_bookmarks_service, mock_duckdb_store):
    """Test multiple bookmark operations in sequence."""
    with patch("searchat.api.routers.bookmarks.deps.get_bookmarks_service", return_value=mock_bookmarks_service), \
         patch("searchat.api.routers.bookmarks.deps.get_duckdb_store", return_value=mock_duckdb_store):

        # Add first bookmark
        response = client.post("/api/bookmarks", json={"conversation_id": "conv-1", "notes": "First"})
        assert response.status_code == 200

        # Add second bookmark
        response = client.post("/api/bookmarks", json={"conversation_id": "conv-2", "notes": "Second"})
        assert response.status_code == 200

        # Get all bookmarks
        response = client.get("/api/bookmarks")
        assert response.status_code == 200
        assert len(response.json()["bookmarks"]) == 2

        # Update notes
        response = client.patch("/api/bookmarks/conv-1/notes", json={"notes": "Updated"})
        assert response.status_code == 200

        # Delete one
        response = client.delete("/api/bookmarks/conv-2")
        assert response.status_code == 200

        # Verify only one remains
        response = client.get("/api/bookmarks")
        assert response.status_code == 200
        bookmarks = response.json()["bookmarks"]
        assert len(bookmarks) == 1
        assert bookmarks[0]["conversation_id"] == "conv-1"
        assert bookmarks[0]["notes"] == "Updated"
