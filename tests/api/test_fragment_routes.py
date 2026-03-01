"""Tests for fragment router — HTMX HTML partial endpoints."""
from __future__ import annotations

from datetime import datetime
from unittest.mock import Mock, patch

import pytest
from fastapi.testclient import TestClient

from searchat.api.app import app
from searchat.models.domain import SearchResult, SearchResults


@pytest.fixture
def client():
    return TestClient(app)


# ---------------------------------------------------------------------------
# Search fragments
# ---------------------------------------------------------------------------


class TestSearchResults:
    def test_empty_query_returns_html(self, client: TestClient):
        resp = client.get("/fragments/search-results")
        assert resp.status_code == 200
        assert "text/html" in resp.headers["content-type"]

    def test_with_query_no_engine(self, client: TestClient):
        resp = client.get("/fragments/search-results?q=test")
        assert resp.status_code == 200
        assert "text/html" in resp.headers["content-type"]

    @patch("searchat.api.routers.fragments.deps.get_search_engine")
    def test_with_query_and_engine(self, mock_engine_getter, client: TestClient):
        engine = Mock()
        now = datetime(2025, 1, 1)
        engine.search.return_value = SearchResults(
            results=[
                SearchResult(
                    conversation_id="c1",
                    project_id="proj",
                    title="Test Conv",
                    created_at=now,
                    updated_at=now,
                    message_count=5,
                    file_path="test.jsonl",
                    score=0.95,
                    snippet="Some text",
                ),
            ],
            total_count=1,
            search_time_ms=12.5,
            mode_used="hybrid",
        )
        mock_engine_getter.return_value = engine
        resp = client.get("/fragments/search-results?q=test&mode=hybrid")
        assert resp.status_code == 200
        assert "Test Conv" in resp.text


class TestSuggestions:
    def test_empty_query(self, client: TestClient):
        resp = client.get("/fragments/suggestions?q=")
        assert resp.status_code == 200
        assert "text/html" in resp.headers["content-type"]

    def test_short_query(self, client: TestClient):
        resp = client.get("/fragments/suggestions?q=a")
        assert resp.status_code == 200


class TestProjectOptions:
    def test_returns_html(self, client: TestClient):
        resp = client.get("/fragments/project-options")
        assert resp.status_code == 200
        assert "text/html" in resp.headers["content-type"]

    @patch("searchat.api.routers.fragments.deps.get_search_engine")
    def test_with_projects(self, mock_engine_getter, client: TestClient):
        engine = Mock()
        engine.get_projects.return_value = ["proj-a", "proj-b"]
        mock_engine_getter.return_value = engine
        resp = client.get("/fragments/project-options")
        assert resp.status_code == 200
        assert "proj-a" in resp.text
        assert "proj-b" in resp.text


class TestProjectSummary:
    def test_no_project(self, client: TestClient):
        resp = client.get("/fragments/project-summary")
        assert resp.status_code == 200

    def test_with_project_no_engine(self, client: TestClient):
        resp = client.get("/fragments/project-summary?project=test")
        assert resp.status_code == 200


class TestPagination:
    def test_returns_html(self, client: TestClient):
        resp = client.get("/fragments/pagination?page=1&total_pages=5&q=test")
        assert resp.status_code == 200
        assert "text/html" in resp.headers["content-type"]


# ---------------------------------------------------------------------------
# Bookmarks fragments
# ---------------------------------------------------------------------------


class TestBookmarksList:
    def test_returns_html(self, client: TestClient):
        resp = client.get("/fragments/bookmarks-list")
        assert resp.status_code == 200
        assert "text/html" in resp.headers["content-type"]

    @patch("searchat.api.routers.fragments.deps.get_bookmarks_service")
    def test_with_bookmarks(self, mock_bm_getter, client: TestClient):
        svc = Mock()
        svc.list_bookmarks.return_value = [
            {"conversation_id": "c1", "added_at": "2025-01-01", "notes": "test note"},
        ]
        mock_bm_getter.return_value = svc
        resp = client.get("/fragments/bookmarks-list")
        assert resp.status_code == 200


class TestBookmarkToggle:
    @patch("searchat.api.routers.fragments.deps.get_bookmarks_service")
    def test_toggle_adds_bookmark(self, mock_bm_getter, client: TestClient):
        svc = Mock()
        svc.get_bookmark.return_value = None
        mock_bm_getter.return_value = svc
        resp = client.post("/fragments/bookmark-toggle/c1")
        assert resp.status_code == 200
        svc.add_bookmark.assert_called_once_with("c1")

    @patch("searchat.api.routers.fragments.deps.get_bookmarks_service")
    def test_toggle_removes_bookmark(self, mock_bm_getter, client: TestClient):
        svc = Mock()
        svc.get_bookmark.return_value = {"conversation_id": "c1"}
        mock_bm_getter.return_value = svc
        resp = client.post("/fragments/bookmark-toggle/c1")
        assert resp.status_code == 200
        svc.remove_bookmark.assert_called_once_with("c1")


# ---------------------------------------------------------------------------
# Backup fragments
# ---------------------------------------------------------------------------


class TestBackupList:
    def test_returns_html(self, client: TestClient):
        resp = client.get("/fragments/backup-list")
        assert resp.status_code == 200
        assert "text/html" in resp.headers["content-type"]


class TestBackupCreate:
    def test_no_service(self, client: TestClient):
        resp = client.post("/fragments/backup-create")
        assert resp.status_code == 200
        assert "not available" in resp.text.lower() or "error" in resp.text.lower() or "Backup" in resp.text


# ---------------------------------------------------------------------------
# Saved queries fragments
# ---------------------------------------------------------------------------


class TestSavedQueriesList:
    def test_returns_html(self, client: TestClient):
        resp = client.get("/fragments/saved-queries-list")
        assert resp.status_code == 200
        assert "text/html" in resp.headers["content-type"]


class TestSavedQueryDelete:
    @patch("searchat.api.routers.fragments.deps.get_saved_queries_service")
    def test_delete(self, mock_sq_getter, client: TestClient):
        svc = Mock()
        svc.list_queries.return_value = []
        mock_sq_getter.return_value = svc
        resp = client.delete("/fragments/saved-query/q1")
        assert resp.status_code == 200
        svc.delete_query.assert_called_once_with("q1")


# ---------------------------------------------------------------------------
# Index missing
# ---------------------------------------------------------------------------


class TestIndexMissing:
    def test_returns_html(self, client: TestClient):
        resp = client.post("/fragments/index-missing")
        assert resp.status_code == 200
        assert "text/html" in resp.headers["content-type"]


# ---------------------------------------------------------------------------
# Analytics
# ---------------------------------------------------------------------------


class TestAnalyticsDashboard:
    def test_no_service(self, client: TestClient):
        resp = client.get("/fragments/analytics-dashboard")
        assert resp.status_code == 200
        assert "text/html" in resp.headers["content-type"]

    def test_custom_days(self, client: TestClient):
        resp = client.get("/fragments/analytics-dashboard?days=7")
        assert resp.status_code == 200


# ---------------------------------------------------------------------------
# Dashboards
# ---------------------------------------------------------------------------


class TestDashboardsView:
    def test_no_service(self, client: TestClient):
        resp = client.get("/fragments/dashboards-view")
        assert resp.status_code == 200
        assert "text/html" in resp.headers["content-type"]

    @patch("searchat.api.routers.fragments.deps.get_dashboards_service")
    def test_with_dashboards(self, mock_ds_getter, client: TestClient):
        svc = Mock()
        svc.list_dashboards.return_value = [
            {
                "id": "d1",
                "name": "My Dashboard",
                "description": "Test",
                "created_at": "2025-01-01",
                "layout": {"widgets": []},
            }
        ]
        mock_ds_getter.return_value = svc
        resp = client.get("/fragments/dashboards-view")
        assert resp.status_code == 200
        assert "My Dashboard" in resp.text


# ---------------------------------------------------------------------------
# Expertise
# ---------------------------------------------------------------------------


class TestExpertiseView:
    def test_no_store(self, client: TestClient):
        resp = client.get("/fragments/expertise-view")
        assert resp.status_code == 200
        assert "text/html" in resp.headers["content-type"]


# ---------------------------------------------------------------------------
# Contradictions
# ---------------------------------------------------------------------------


class TestContradictionsView:
    def test_no_store(self, client: TestClient):
        resp = client.get("/fragments/contradictions-view")
        assert resp.status_code == 200
        assert "text/html" in resp.headers["content-type"]


# ---------------------------------------------------------------------------
# Similar conversations
# ---------------------------------------------------------------------------


class TestSimilarConversations:
    def test_no_engine(self, client: TestClient):
        resp = client.get("/fragments/similar/conv-123")
        assert resp.status_code == 200
        assert "text/html" in resp.headers["content-type"]


# ---------------------------------------------------------------------------
# Conversation view
# ---------------------------------------------------------------------------


class TestConversationView:
    def test_no_engine(self, client: TestClient):
        resp = client.get("/fragments/conversation-view/conv-123")
        assert resp.status_code == 200
        assert "text/html" in resp.headers["content-type"]


# ---------------------------------------------------------------------------
# Dataset options
# ---------------------------------------------------------------------------


class TestDatasetOptions:
    def test_returns_html(self, client: TestClient):
        resp = client.get("/fragments/dataset-options")
        assert resp.status_code == 200
        assert "text/html" in resp.headers["content-type"]
        assert "Live Index" in resp.text
