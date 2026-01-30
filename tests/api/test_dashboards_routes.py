"""Unit tests for dashboards API routes."""
from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from searchat.api.app import app
from searchat.models import SearchResult, SearchResults, SearchMode


class InMemoryDashboardsService:
    def __init__(self) -> None:
        self._dashboards: dict[str, dict] = {}

    def list_dashboards(self) -> list[dict]:
        return sorted(self._dashboards.values(), key=lambda d: d["created_at"], reverse=True)

    def get_dashboard(self, dashboard_id: str) -> dict | None:
        return self._dashboards.get(dashboard_id)

    def create_dashboard(self, payload: dict) -> dict:
        dashboard_id = str(uuid4())
        timestamp = datetime.now(timezone.utc).isoformat()
        dashboard = {
            "id": dashboard_id,
            "name": payload["name"],
            "description": payload.get("description"),
            "queries": payload.get("queries", []),
            "layout": payload["layout"],
            "refresh_interval": payload.get("refresh_interval"),
            "created_at": timestamp,
            "updated_at": timestamp,
        }
        self._dashboards[dashboard_id] = dashboard
        return dashboard

    def update_dashboard(self, dashboard_id: str, updates: dict) -> dict | None:
        dashboard = self._dashboards.get(dashboard_id)
        if dashboard is None:
            return None
        for key, value in updates.items():
            dashboard[key] = value
        self._dashboards[dashboard_id] = dashboard
        return dashboard

    def delete_dashboard(self, dashboard_id: str) -> bool:
        if dashboard_id in self._dashboards:
            del self._dashboards[dashboard_id]
            return True
        return False


class InMemorySavedQueriesService:
    def __init__(self, query: dict) -> None:
        self._queries = {query["id"]: query}

    def get_query(self, query_id: str) -> dict | None:
        return self._queries.get(query_id)


class FakeSearchEngine:
    def __init__(self, results: SearchResults) -> None:
        self._results = results

    def search(self, q: str, mode: SearchMode, filters) -> SearchResults:
        return self._results


@pytest.fixture
def client():
    return TestClient(app)


def _enabled_config():
    return SimpleNamespace(dashboards=SimpleNamespace(enabled=True))


def test_dashboards_crud_flow(client, monkeypatch):
    dashboards_service = InMemoryDashboardsService()
    monkeypatch.setattr(
        "searchat.api.routers.dashboards.deps.get_dashboards_service",
        lambda: dashboards_service,
    )
    monkeypatch.setattr("searchat.api.routers.dashboards.deps.get_config", _enabled_config)

    payload = {
        "name": "Daily Ops",
        "description": "Top ops queries",
        "queries": ["q-1"],
        "layout": {"widgets": [{"query_id": "q-1"}]},
        "refresh_interval": 120,
    }

    created = client.post("/api/dashboards", json=payload)
    assert created.status_code == 200
    dashboard_id = created.json()["dashboard"]["id"]

    listing = client.get("/api/dashboards")
    assert listing.status_code == 200
    assert listing.json()["total"] == 1

    fetched = client.get(f"/api/dashboards/{dashboard_id}")
    assert fetched.status_code == 200
    assert fetched.json()["dashboard"]["name"] == "Daily Ops"

    updated = client.put(f"/api/dashboards/{dashboard_id}", json={"name": "Daily Ops v2"})
    assert updated.status_code == 200
    assert updated.json()["dashboard"]["name"] == "Daily Ops v2"

    deleted = client.delete(f"/api/dashboards/{dashboard_id}")
    assert deleted.status_code == 200

    listing_after = client.get("/api/dashboards")
    assert listing_after.status_code == 200
    assert listing_after.json()["total"] == 0


def test_dashboards_render_flow(client, monkeypatch):
    dashboards_service = InMemoryDashboardsService()
    dashboard = dashboards_service.create_dashboard(
        {
            "name": "Release",
            "description": None,
            "queries": ["q-1"],
            "layout": {"widgets": [{"id": "w-1", "query_id": "q-1", "limit": 5}]},
            "refresh_interval": None,
        }
    )

    query = {
        "id": "q-1",
        "name": "Release Check",
        "query": "deployment",
        "filters": {"project": "proj", "tool": "claude", "sort_by": "relevance"},
        "mode": "keyword",
    }
    saved_queries_service = InMemorySavedQueriesService(query)

    now = datetime.now(timezone.utc)
    result = SearchResult(
        conversation_id="conv-1",
        project_id="proj",
        title="Deploy log",
        created_at=now,
        updated_at=now,
        message_count=4,
        file_path="/home/user/.claude/projects/proj/conv.jsonl",
        score=0.88,
        snippet="Deployment steps",
        message_start_index=0,
        message_end_index=1,
    )
    search_results = SearchResults(
        results=[result],
        total_count=1,
        search_time_ms=2.0,
        mode_used="keyword",
    )

    monkeypatch.setattr(
        "searchat.api.routers.dashboards.deps.get_dashboards_service",
        lambda: dashboards_service,
    )
    monkeypatch.setattr(
        "searchat.api.routers.dashboards.deps.get_saved_queries_service",
        lambda: saved_queries_service,
    )
    monkeypatch.setattr(
        "searchat.api.routers.dashboards.get_or_create_search_engine",
        lambda: FakeSearchEngine(search_results),
    )
    monkeypatch.setattr("searchat.api.routers.dashboards.deps.get_config", _enabled_config)

    response = client.get(f"/api/dashboards/{dashboard['id']}/render")
    assert response.status_code == 200
    data = response.json()
    assert data["dashboard"]["id"] == dashboard["id"]
    assert data["widgets"][0]["results"][0]["conversation_id"] == "conv-1"
