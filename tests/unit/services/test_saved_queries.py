"""Tests for searchat.services.saved_queries.SavedQueriesService."""
from __future__ import annotations

import pytest

from searchat.config import Config
from searchat.services.saved_queries import SavedQueriesService


@pytest.fixture
def svc(monkeypatch, tmp_path) -> SavedQueriesService:
    """SavedQueriesService backed by a temporary directory."""
    monkeypatch.setenv("SEARCHAT_DATA_DIR", str(tmp_path))
    config = Config.load()
    monkeypatch.setattr(config.paths, "search_directory", str(tmp_path))
    return SavedQueriesService(config)


def _make_payload(
    name: str = "My Query",
    query: str = "search term",
    mode: str = "hybrid",
    filters: dict | None = None,
) -> dict:
    if filters is None:
        filters = {"tool": "claude"}
    return {"name": name, "query": query, "mode": mode, "filters": filters}


class TestCreateQuery:
    """Tests for SavedQueriesService.create_query."""

    def test_basic_create(self, svc):
        q = svc.create_query(_make_payload())
        assert q["name"] == "My Query"
        assert q["query"] == "search term"
        assert q["mode"] == "hybrid"
        assert q["use_count"] == 0
        assert q["last_used"] is None

    def test_create_requires_name(self, svc):
        with pytest.raises(ValueError, match="name is required"):
            svc.create_query(_make_payload(name=""))

    def test_create_requires_query_text(self, svc):
        payload = _make_payload()
        payload["query"] = None
        with pytest.raises(ValueError, match="text is required"):
            svc.create_query(payload)

    def test_create_requires_filters(self, svc):
        payload = _make_payload()
        payload["filters"] = "invalid"
        with pytest.raises(ValueError, match="filters must be provided"):
            svc.create_query(payload)

    def test_create_requires_mode(self, svc):
        with pytest.raises(ValueError, match="mode is required"):
            svc.create_query(_make_payload(mode=""))


class TestGetQuery:
    """Tests for SavedQueriesService.get_query."""

    def test_get_existing(self, svc):
        created = svc.create_query(_make_payload())
        fetched = svc.get_query(created["id"])
        assert fetched is not None
        assert fetched["id"] == created["id"]

    def test_get_nonexistent(self, svc):
        assert svc.get_query("nonexistent") is None


class TestListQueries:
    """Tests for SavedQueriesService.list_queries."""

    def test_empty_list(self, svc):
        assert svc.list_queries() == []

    def test_sorted_by_created_at_descending(self, svc):
        svc.create_query(_make_payload(name="First"))
        svc.create_query(_make_payload(name="Second"))
        queries = svc.list_queries()
        assert len(queries) == 2
        assert queries[0]["name"] == "Second"


class TestUpdateQuery:
    """Tests for SavedQueriesService.update_query."""

    def test_update_name(self, svc):
        created = svc.create_query(_make_payload())
        updated = svc.update_query(created["id"], {"name": "Renamed"})
        assert updated is not None
        assert updated["name"] == "Renamed"

    def test_update_nonexistent(self, svc):
        assert svc.update_query("missing", {"name": "X"}) is None

    def test_update_rejects_empty_name(self, svc):
        created = svc.create_query(_make_payload())
        with pytest.raises(ValueError, match="name is required"):
            svc.update_query(created["id"], {"name": ""})

    def test_update_query_text(self, svc):
        created = svc.create_query(_make_payload())
        updated = svc.update_query(created["id"], {"query": "new search"})
        assert updated["query"] == "new search"

    def test_update_rejects_non_string_query(self, svc):
        created = svc.create_query(_make_payload())
        with pytest.raises(ValueError, match="text is required"):
            svc.update_query(created["id"], {"query": 123})

    def test_update_rejects_non_dict_filters(self, svc):
        created = svc.create_query(_make_payload())
        with pytest.raises(ValueError, match="filters must be provided"):
            svc.update_query(created["id"], {"filters": "bad"})

    def test_update_rejects_empty_mode(self, svc):
        created = svc.create_query(_make_payload())
        with pytest.raises(ValueError, match="mode is required"):
            svc.update_query(created["id"], {"mode": ""})

    def test_update_multiple_fields(self, svc):
        created = svc.create_query(_make_payload())
        updated = svc.update_query(created["id"], {
            "name": "Updated",
            "description": "New desc",
            "mode": "keyword",
        })
        assert updated["name"] == "Updated"
        assert updated["description"] == "New desc"
        assert updated["mode"] == "keyword"


class TestDeleteQuery:
    """Tests for SavedQueriesService.delete_query."""

    def test_delete_existing(self, svc):
        created = svc.create_query(_make_payload())
        assert svc.delete_query(created["id"]) is True
        assert svc.get_query(created["id"]) is None

    def test_delete_nonexistent(self, svc):
        assert svc.delete_query("missing") is False


class TestRecordUse:
    """Tests for SavedQueriesService.record_use."""

    def test_increments_use_count(self, svc):
        created = svc.create_query(_make_payload())
        updated = svc.record_use(created["id"])
        assert updated is not None
        assert updated["use_count"] == 1
        assert updated["last_used"] is not None

    def test_multiple_uses(self, svc):
        created = svc.create_query(_make_payload())
        svc.record_use(created["id"])
        updated = svc.record_use(created["id"])
        assert updated["use_count"] == 2

    def test_record_use_nonexistent(self, svc):
        assert svc.record_use("missing") is None
