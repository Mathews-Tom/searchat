"""Tests for searchat.services.dashboards.DashboardsService."""
from __future__ import annotations

import pytest

from searchat.config import Config
from searchat.services.dashboards import DashboardsService


@pytest.fixture
def svc(monkeypatch, tmp_path) -> DashboardsService:
    """DashboardsService backed by a temporary directory."""
    monkeypatch.setenv("SEARCHAT_DATA_DIR", str(tmp_path))
    config = Config.load()
    monkeypatch.setattr(config.paths, "search_directory", str(tmp_path))
    return DashboardsService(config)


def _make_payload(
    name: str = "My Dashboard",
    layout: dict | None = None,
    queries: list | None = None,
) -> dict:
    if layout is None:
        layout = {"widgets": [{"query_id": "q1"}]}
    return {"name": name, "layout": layout, "queries": queries}


class TestCreateDashboard:
    """Tests for DashboardsService.create_dashboard."""

    def test_basic_create(self, svc):
        dashboard = svc.create_dashboard(_make_payload())
        assert dashboard["name"] == "My Dashboard"
        assert "id" in dashboard
        assert dashboard["created_at"] == dashboard["updated_at"]

    def test_create_with_description(self, svc):
        payload = _make_payload()
        payload["description"] = "Test description"
        dashboard = svc.create_dashboard(payload)
        assert dashboard["description"] == "Test description"

    def test_create_with_refresh_interval(self, svc):
        payload = _make_payload()
        payload["refresh_interval"] = 30
        dashboard = svc.create_dashboard(payload)
        assert dashboard["refresh_interval"] == 30

    def test_create_requires_name(self, svc):
        payload = _make_payload()
        payload["name"] = ""
        with pytest.raises(ValueError, match="name is required"):
            svc.create_dashboard(payload)

    def test_create_rejects_missing_name(self, svc):
        payload = _make_payload()
        del payload["name"]
        with pytest.raises(ValueError, match="name is required"):
            svc.create_dashboard(payload)

    def test_create_requires_layout(self, svc):
        with pytest.raises(ValueError, match="layout is required"):
            svc.create_dashboard({"name": "X", "layout": "invalid"})

    def test_create_requires_widgets(self, svc):
        with pytest.raises(ValueError, match="widgets are required"):
            svc.create_dashboard({"name": "X", "layout": {"widgets": []}})

    def test_create_rejects_non_int_refresh(self, svc):
        payload = _make_payload()
        payload["refresh_interval"] = "slow"
        with pytest.raises(ValueError, match="refresh_interval must be an integer"):
            svc.create_dashboard(payload)


class TestGetDashboard:
    """Tests for DashboardsService.get_dashboard."""

    def test_get_existing(self, svc):
        created = svc.create_dashboard(_make_payload())
        fetched = svc.get_dashboard(created["id"])
        assert fetched is not None
        assert fetched["id"] == created["id"]

    def test_get_nonexistent(self, svc):
        assert svc.get_dashboard("nonexistent") is None


class TestListDashboards:
    """Tests for DashboardsService.list_dashboards."""

    def test_empty_list(self, svc):
        assert svc.list_dashboards() == []

    def test_sorted_by_created_at_descending(self, svc):
        import time

        svc.create_dashboard(_make_payload(name="First"))
        time.sleep(0.05)  # ensure distinct timestamps on all platforms
        svc.create_dashboard(_make_payload(name="Second"))
        dashboards = svc.list_dashboards()
        assert len(dashboards) == 2
        assert dashboards[0]["name"] == "Second"
        assert dashboards[1]["name"] == "First"


class TestUpdateDashboard:
    """Tests for DashboardsService.update_dashboard."""

    def test_update_name(self, svc):
        created = svc.create_dashboard(_make_payload())
        updated = svc.update_dashboard(created["id"], {"name": "Renamed"})
        assert updated is not None
        assert updated["name"] == "Renamed"

    def test_update_nonexistent(self, svc):
        assert svc.update_dashboard("missing", {"name": "X"}) is None

    def test_update_rejects_empty_name(self, svc):
        created = svc.create_dashboard(_make_payload())
        with pytest.raises(ValueError, match="name is required"):
            svc.update_dashboard(created["id"], {"name": ""})

    def test_update_layout(self, svc):
        created = svc.create_dashboard(_make_payload())
        new_layout = {"widgets": [{"query_id": "q2"}]}
        updated = svc.update_dashboard(created["id"], {"layout": new_layout})
        assert updated is not None
        assert updated["layout"]["widgets"][0]["query_id"] == "q2"

    def test_update_rejects_non_int_refresh(self, svc):
        created = svc.create_dashboard(_make_payload())
        with pytest.raises(ValueError, match="refresh_interval must be an integer"):
            svc.update_dashboard(created["id"], {"refresh_interval": 3.5})

    def test_update_description(self, svc):
        created = svc.create_dashboard(_make_payload())
        updated = svc.update_dashboard(created["id"], {"description": "New desc"})
        assert updated["description"] == "New desc"


class TestDeleteDashboard:
    """Tests for DashboardsService.delete_dashboard."""

    def test_delete_existing(self, svc):
        created = svc.create_dashboard(_make_payload())
        assert svc.delete_dashboard(created["id"]) is True
        assert svc.get_dashboard(created["id"]) is None

    def test_delete_nonexistent(self, svc):
        assert svc.delete_dashboard("missing") is False


class TestNormalizeLayout:
    """Tests for DashboardsService._normalize_layout."""

    def test_widget_with_all_fields(self, svc):
        layout = {
            "widgets": [{
                "query_id": "q1",
                "title": "Widget Title",
                "limit": 10,
                "sort_by": "date",
                "layout": {"x": 0, "y": 0},
                "id": "w1",
            }],
            "columns": 3,
        }
        result = svc._normalize_layout(layout)
        assert result["columns"] == 3
        assert result["widgets"][0]["id"] == "w1"
        assert result["widgets"][0]["title"] == "Widget Title"

    def test_widget_non_dict_rejected(self, svc):
        with pytest.raises(ValueError, match="widget must be an object"):
            svc._normalize_layout({"widgets": ["not_a_dict"]})

    def test_widget_missing_query_id(self, svc):
        with pytest.raises(ValueError, match="query_id is required"):
            svc._normalize_layout({"widgets": [{"title": "X"}]})

    def test_widget_non_string_title(self, svc):
        with pytest.raises(ValueError, match="title must be a string"):
            svc._normalize_layout({"widgets": [{"query_id": "q1", "title": 123}]})

    def test_widget_non_int_limit(self, svc):
        with pytest.raises(ValueError, match="limit must be an integer"):
            svc._normalize_layout({"widgets": [{"query_id": "q1", "limit": "ten"}]})

    def test_widget_non_string_sort_by(self, svc):
        with pytest.raises(ValueError, match="sort_by must be a string"):
            svc._normalize_layout({"widgets": [{"query_id": "q1", "sort_by": 42}]})

    def test_widget_non_dict_layout(self, svc):
        with pytest.raises(ValueError, match="widget layout must be an object"):
            svc._normalize_layout({"widgets": [{"query_id": "q1", "layout": "flat"}]})

    def test_widget_non_string_id(self, svc):
        with pytest.raises(ValueError, match="widget id must be a string"):
            svc._normalize_layout({"widgets": [{"query_id": "q1", "id": 999}]})

    def test_non_int_columns(self, svc):
        with pytest.raises(ValueError, match="columns must be an integer"):
            svc._normalize_layout({"widgets": [{"query_id": "q1"}], "columns": "two"})


class TestNormalizeQueries:
    """Tests for DashboardsService._normalize_queries."""

    def test_queries_from_widgets(self, svc):
        layout = {"widgets": [{"query_id": "q1"}, {"query_id": "q2"}]}
        result = svc._normalize_queries(None, layout)
        assert result == ["q1", "q2"]

    def test_explicit_queries_validated(self, svc):
        layout = {"widgets": [{"query_id": "q1"}]}
        result = svc._normalize_queries(["q1", "extra"], layout)
        assert result == ["q1", "extra"]

    def test_explicit_queries_must_include_widget_ids(self, svc):
        layout = {"widgets": [{"query_id": "q1"}, {"query_id": "q2"}]}
        with pytest.raises(ValueError, match="must include all widget query ids"):
            svc._normalize_queries(["q1"], layout)

    def test_non_list_queries_rejected(self, svc):
        with pytest.raises(ValueError, match="must be a list"):
            svc._normalize_queries("q1", {"widgets": []})

    def test_non_string_query_id_rejected(self, svc):
        with pytest.raises(ValueError, match="must be a list of strings"):
            svc._normalize_queries([123], {"widgets": []})

    def test_deduplicates_queries(self, svc):
        layout = {"widgets": [{"query_id": "q1"}]}
        result = svc._normalize_queries(["q1", "q1"], layout)
        assert result == ["q1"]
