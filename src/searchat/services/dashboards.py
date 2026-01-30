"""Dashboard service for managing saved layouts."""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

from searchat.config import Config


class DashboardsService:
    """Service for managing dashboards stored on disk."""

    def __init__(self, config: Config) -> None:
        self._config = config
        self._dashboards_file = Path(config.paths.search_directory) / "dashboards.json"
        self._ensure_file()

    def _ensure_file(self) -> None:
        if not self._dashboards_file.exists():
            self._dashboards_file.parent.mkdir(parents=True, exist_ok=True)
            self._save_dashboards({})

    def _load_dashboards(self) -> dict[str, dict[str, Any]]:
        with open(self._dashboards_file, encoding="utf-8") as handle:
            data = json.load(handle)
        if not isinstance(data, dict):
            raise ValueError("Dashboards file is invalid.")
        return data

    def _save_dashboards(self, dashboards: dict[str, dict[str, Any]]) -> None:
        with open(self._dashboards_file, "w", encoding="utf-8") as handle:
            json.dump(dashboards, handle, indent=2)

    def list_dashboards(self) -> list[dict[str, Any]]:
        dashboards = self._load_dashboards()
        dashboard_list = list(dashboards.values())
        for dashboard in dashboard_list:
            created_at = dashboard.get("created_at")
            if not isinstance(created_at, str) or not created_at:
                raise ValueError("Dashboard is missing created_at.")
        dashboard_list.sort(key=lambda d: d["created_at"], reverse=True)
        return dashboard_list

    def get_dashboard(self, dashboard_id: str) -> dict[str, Any] | None:
        dashboards = self._load_dashboards()
        return dashboards.get(dashboard_id)

    def create_dashboard(self, payload: dict[str, Any]) -> dict[str, Any]:
        name = payload.get("name")
        if not isinstance(name, str) or not name.strip():
            raise ValueError("Dashboard name is required.")

        layout = self._normalize_layout(payload.get("layout"))
        queries = self._normalize_queries(payload.get("queries"), layout)

        refresh_interval = payload.get("refresh_interval")
        if refresh_interval is not None and not isinstance(refresh_interval, int):
            raise ValueError("Dashboard refresh_interval must be an integer.")

        dashboards = self._load_dashboards()
        dashboard_id = str(uuid4())
        timestamp = datetime.now().isoformat()
        dashboard = {
            "id": dashboard_id,
            "name": name,
            "description": payload.get("description"),
            "queries": queries,
            "layout": layout,
            "refresh_interval": refresh_interval,
            "created_at": timestamp,
            "updated_at": timestamp,
        }
        dashboards[dashboard_id] = dashboard
        self._save_dashboards(dashboards)
        return dashboard

    def update_dashboard(self, dashboard_id: str, updates: dict[str, Any]) -> dict[str, Any] | None:
        dashboards = self._load_dashboards()
        dashboard = dashboards.get(dashboard_id)
        if dashboard is None:
            return None

        if "name" in updates:
            name = updates["name"]
            if not isinstance(name, str) or not name.strip():
                raise ValueError("Dashboard name is required.")

        if "refresh_interval" in updates:
            refresh_interval = updates["refresh_interval"]
            if refresh_interval is not None and not isinstance(refresh_interval, int):
                raise ValueError("Dashboard refresh_interval must be an integer.")

        layout: dict[str, Any] | None = None
        existing_layout = dashboard.get("layout")
        if isinstance(existing_layout, dict):
            layout = existing_layout
        if "layout" in updates:
            layout = self._normalize_layout(updates.get("layout"))
            dashboard["layout"] = layout

        if "queries" in updates or "layout" in updates:
            if layout is None:
                raise ValueError("Dashboard layout is required.")
            dashboard["queries"] = self._normalize_queries(updates.get("queries"), layout)

        for field in ("name", "description", "refresh_interval"):
            if field in updates:
                dashboard[field] = updates[field]

        dashboard["updated_at"] = datetime.now().isoformat()
        dashboards[dashboard_id] = dashboard
        self._save_dashboards(dashboards)
        return dashboard

    def delete_dashboard(self, dashboard_id: str) -> bool:
        dashboards = self._load_dashboards()
        if dashboard_id in dashboards:
            del dashboards[dashboard_id]
            self._save_dashboards(dashboards)
            return True
        return False

    def _normalize_layout(self, layout: Any) -> dict[str, Any]:
        if not isinstance(layout, dict):
            raise ValueError("Dashboard layout is required.")
        widgets = layout.get("widgets")
        if not isinstance(widgets, list) or not widgets:
            raise ValueError("Dashboard layout widgets are required.")

        normalized_widgets: list[dict[str, Any]] = []
        for widget in widgets:
            if not isinstance(widget, dict):
                raise ValueError("Dashboard widget must be an object.")
            query_id = widget.get("query_id")
            if not isinstance(query_id, str) or not query_id.strip():
                raise ValueError("Dashboard widget query_id is required.")

            title = widget.get("title")
            if title is not None and not isinstance(title, str):
                raise ValueError("Dashboard widget title must be a string.")

            limit = widget.get("limit")
            if limit is not None and not isinstance(limit, int):
                raise ValueError("Dashboard widget limit must be an integer.")

            sort_by = widget.get("sort_by")
            if sort_by is not None and not isinstance(sort_by, str):
                raise ValueError("Dashboard widget sort_by must be a string.")

            widget_layout = widget.get("layout")
            if widget_layout is not None and not isinstance(widget_layout, dict):
                raise ValueError("Dashboard widget layout must be an object.")

            widget_id = widget.get("id")
            if widget_id is not None and not isinstance(widget_id, str):
                raise ValueError("Dashboard widget id must be a string.")

            normalized_widgets.append(
                {
                    "id": widget_id or str(uuid4()),
                    "query_id": query_id,
                    "title": title,
                    "limit": limit,
                    "sort_by": sort_by,
                    "layout": widget_layout,
                }
            )

        normalized_layout: dict[str, Any] = {"widgets": normalized_widgets}
        columns = layout.get("columns")
        if columns is not None:
            if not isinstance(columns, int):
                raise ValueError("Dashboard layout columns must be an integer.")
            normalized_layout["columns"] = columns
        return normalized_layout

    def _normalize_queries(self, queries: Any, layout: dict[str, Any]) -> list[str]:
        if queries is not None and not isinstance(queries, list):
            raise ValueError("Dashboard queries must be a list of strings.")
        query_list: list[str] = []
        if isinstance(queries, list):
            for query_id in queries:
                if not isinstance(query_id, str) or not query_id.strip():
                    raise ValueError("Dashboard queries must be a list of strings.")
                if query_id not in query_list:
                    query_list.append(query_id)

        widget_queries: list[str] = []
        for widget in layout.get("widgets", []):
            query_id = widget.get("query_id")
            if isinstance(query_id, str) and query_id not in widget_queries:
                widget_queries.append(query_id)

        if query_list:
            missing = [query_id for query_id in widget_queries if query_id not in query_list]
            if missing:
                raise ValueError("Dashboard queries must include all widget query ids.")
            return query_list
        return widget_queries
