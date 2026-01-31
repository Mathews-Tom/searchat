"""Unit tests for saved queries API routes."""
from __future__ import annotations

from datetime import datetime
from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from searchat.api.app import app


class InMemorySavedQueriesService:
    def __init__(self) -> None:
        self._queries: dict[str, dict] = {}

    def list_queries(self) -> list[dict]:
        return sorted(self._queries.values(), key=lambda q: q["created_at"], reverse=True)

    def create_query(self, payload: dict) -> dict:
        query_id = str(uuid4())
        query = {
            "id": query_id,
            "name": payload["name"],
            "description": payload.get("description"),
            "query": payload["query"],
            "filters": payload["filters"],
            "mode": payload["mode"],
            "created_at": datetime.now().isoformat(),
            "last_used": None,
            "use_count": 0,
        }
        self._queries[query_id] = query
        return query

    def update_query(self, query_id: str, updates: dict) -> dict | None:
        query = self._queries.get(query_id)
        if query is None:
            return None
        for key, value in updates.items():
            query[key] = value
        self._queries[query_id] = query
        return query

    def delete_query(self, query_id: str) -> bool:
        if query_id in self._queries:
            del self._queries[query_id]
            return True
        return False

    def record_use(self, query_id: str) -> dict | None:
        query = self._queries.get(query_id)
        if query is None:
            return None
        query["last_used"] = datetime.now().isoformat()
        query["use_count"] += 1
        self._queries[query_id] = query
        return query


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def queries_service():
    return InMemorySavedQueriesService()


def test_queries_crud_flow(client, queries_service, monkeypatch):
    monkeypatch.setattr("searchat.api.routers.queries.deps.get_saved_queries_service", lambda: queries_service)

    payload = {
        "name": "Release Checks",
        "description": "Release smoke",
        "query": "deployment",
        "filters": {
            "project": "",
            "tool": "",
            "date": "",
            "date_from": "",
            "date_to": "",
            "sort_by": "relevance",
        },
        "mode": "hybrid",
    }

    create = client.post("/api/queries", json=payload)
    assert create.status_code == 200
    query_id = create.json()["query"]["id"]

    listing = client.get("/api/queries")
    assert listing.status_code == 200
    assert listing.json()["total"] == 1

    update = client.put(f"/api/queries/{query_id}", json={"name": "Release Checks v2"})
    assert update.status_code == 200
    assert update.json()["query"]["name"] == "Release Checks v2"

    run = client.post(f"/api/queries/{query_id}/run")
    assert run.status_code == 200
    assert run.json()["query"]["use_count"] == 1

    delete = client.delete(f"/api/queries/{query_id}")
    assert delete.status_code == 200
    assert delete.json()["success"] is True

    listing_after = client.get("/api/queries")
    assert listing_after.status_code == 200
    assert listing_after.json()["total"] == 0


def test_queries_list_returns_500_on_service_error(client, monkeypatch):
    class BoomService:
        def list_queries(self):
            raise RuntimeError("boom")

    monkeypatch.setattr("searchat.api.routers.queries.deps.get_saved_queries_service", lambda: BoomService())
    resp = client.get("/api/queries")
    assert resp.status_code == 500
    assert resp.json()["detail"] == "boom"


def test_queries_create_returns_400_on_value_error(client, monkeypatch):
    class BadService:
        def create_query(self, _payload: dict) -> dict:
            raise ValueError("invalid")

    monkeypatch.setattr("searchat.api.routers.queries.deps.get_saved_queries_service", lambda: BadService())
    resp = client.post(
        "/api/queries",
        json={
            "name": "n",
            "description": None,
            "query": "q",
            "filters": {},
            "mode": "hybrid",
        },
    )
    assert resp.status_code == 400
    assert resp.json()["detail"] == "invalid"


def test_queries_update_returns_404_when_not_found(client, monkeypatch):
    service = SimpleNamespace(update_query=lambda _qid, _updates: None)
    monkeypatch.setattr("searchat.api.routers.queries.deps.get_saved_queries_service", lambda: service)
    resp = client.put("/api/queries/missing", json={"name": "x"})
    assert resp.status_code == 404
    assert resp.json()["detail"] == "Saved query not found"


def test_queries_delete_returns_404_when_not_found(client, monkeypatch):
    service = SimpleNamespace(delete_query=lambda _qid: False)
    monkeypatch.setattr("searchat.api.routers.queries.deps.get_saved_queries_service", lambda: service)
    resp = client.delete("/api/queries/missing")
    assert resp.status_code == 404
    assert resp.json()["detail"] == "Saved query not found"


def test_queries_run_returns_404_when_not_found(client, monkeypatch):
    service = SimpleNamespace(record_use=lambda _qid: None)
    monkeypatch.setattr("searchat.api.routers.queries.deps.get_saved_queries_service", lambda: service)
    resp = client.post("/api/queries/missing/run")
    assert resp.status_code == 404
    assert resp.json()["detail"] == "Saved query not found"
