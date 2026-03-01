"""Dashboards endpoints for widget-based saved query layouts."""
from __future__ import annotations

import json
from typing import Any

from fastapi import APIRouter, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel, Field

from searchat.config.constants import VALID_TOOL_NAMES
import searchat.api.dependencies as deps
from searchat.api.dependencies import (
    get_or_create_search_engine,
    get_search_engine,
)
from searchat.api.utils import (
    parse_date_filter,
    check_semantic_readiness,
    sort_results,
    search_result_to_response,
)
from searchat.models import SearchFilters, SearchMode


router = APIRouter()


class DashboardWidgetRequest(BaseModel):
    id: str | None = None
    query_id: str
    title: str | None = None
    limit: int | None = Field(default=5, ge=1, le=100)
    sort_by: str | None = None
    layout: dict[str, int] | None = None


class DashboardLayoutRequest(BaseModel):
    widgets: list[DashboardWidgetRequest] = Field(min_length=1, max_length=50)
    columns: int | None = Field(default=None, ge=1, le=6)


class DashboardCreateRequest(BaseModel):
    name: str
    description: str | None = None
    layout: DashboardLayoutRequest
    queries: list[str] | None = None
    refresh_interval: int | None = Field(default=None, ge=1, le=86400)


class DashboardUpdateRequest(BaseModel):
    name: str | None = None
    description: str | None = None
    layout: DashboardLayoutRequest | None = None
    queries: list[str] | None = None
    refresh_interval: int | None = Field(default=None, ge=1, le=86400)


@router.get("/dashboards")
async def list_dashboards():
    config = deps.get_config()
    if not config.dashboards.enabled:
        raise HTTPException(status_code=404, detail="Dashboards are disabled")

    try:
        service = deps.get_dashboards_service()
        dashboards = service.list_dashboards()
        return {"total": len(dashboards), "dashboards": dashboards}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.post("/dashboards")
async def create_dashboard(request: DashboardCreateRequest):
    config = deps.get_config()
    if not config.dashboards.enabled:
        raise HTTPException(status_code=404, detail="Dashboards are disabled")

    try:
        service = deps.get_dashboards_service()
        dashboard = service.create_dashboard(request.model_dump())
        return {"success": True, "dashboard": dashboard}
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.get("/dashboards/{dashboard_id}")
async def get_dashboard(dashboard_id: str):
    config = deps.get_config()
    if not config.dashboards.enabled:
        raise HTTPException(status_code=404, detail="Dashboards are disabled")

    try:
        service = deps.get_dashboards_service()
        dashboard = service.get_dashboard(dashboard_id)
        if dashboard is None:
            raise HTTPException(status_code=404, detail="Dashboard not found")
        return {"dashboard": dashboard}
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.put("/dashboards/{dashboard_id}")
async def update_dashboard(dashboard_id: str, request: DashboardUpdateRequest):
    config = deps.get_config()
    if not config.dashboards.enabled:
        raise HTTPException(status_code=404, detail="Dashboards are disabled")

    try:
        service = deps.get_dashboards_service()
        updates = {k: v for k, v in request.model_dump().items() if v is not None}
        dashboard = service.update_dashboard(dashboard_id, updates)
        if dashboard is None:
            raise HTTPException(status_code=404, detail="Dashboard not found")
        return {"success": True, "dashboard": dashboard}
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.delete("/dashboards/{dashboard_id}")
async def delete_dashboard(dashboard_id: str):
    config = deps.get_config()
    if not config.dashboards.enabled:
        raise HTTPException(status_code=404, detail="Dashboards are disabled")

    try:
        service = deps.get_dashboards_service()
        removed = service.delete_dashboard(dashboard_id)
        if not removed:
            raise HTTPException(status_code=404, detail="Dashboard not found")
        return {"success": True}
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.get("/dashboards/{dashboard_id}/export")
async def export_dashboard(dashboard_id: str):
    config = deps.get_config()
    if not config.dashboards.enabled:
        raise HTTPException(status_code=404, detail="Dashboards are disabled")

    try:
        service = deps.get_dashboards_service()
        dashboard = service.get_dashboard(dashboard_id)
        if dashboard is None:
            raise HTTPException(status_code=404, detail="Dashboard not found")
        content = json.dumps(dashboard, indent=2).encode("utf-8")
        return Response(
            content=content,
            media_type="application/json",
            headers={
                "Content-Disposition": f"attachment; filename=dashboard_{dashboard_id}.json",
            },
        )
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.get("/dashboards/{dashboard_id}/render")
async def render_dashboard(dashboard_id: str):
    config = deps.get_config()
    if not config.dashboards.enabled:
        raise HTTPException(status_code=404, detail="Dashboards are disabled")

    try:
        dashboards_service = deps.get_dashboards_service()
        saved_queries = deps.get_saved_queries_service()
        dashboard = dashboards_service.get_dashboard(dashboard_id)
        if dashboard is None:
            raise HTTPException(status_code=404, detail="Dashboard not found")

        widgets = _ensure_widgets(dashboard)
        widget_requests: list[dict[str, Any]] = []
        needs_semantic = False

        for widget in widgets:
            query_id = widget.get("query_id")
            query = saved_queries.get_query(query_id) if isinstance(query_id, str) else None
            if query is None:
                raise HTTPException(status_code=400, detail=f"Saved query {query_id} not found")

            query_text = query.get("query")
            if not isinstance(query_text, str):
                raise HTTPException(status_code=400, detail=f"Saved query {query_id} is invalid")

            mode = _parse_mode(query.get("mode"))
            if query_text.strip() == "*":
                mode = SearchMode.KEYWORD
            if mode in (SearchMode.HYBRID, SearchMode.SEMANTIC):
                needs_semantic = True

            widget_requests.append({"widget": widget, "query": query, "mode": mode})

        if needs_semantic:
            not_ready = check_semantic_readiness()
            if not_ready is not None:
                return not_ready
            search_engine = get_search_engine()
        else:
            search_engine = get_or_create_search_engine()

        rendered_widgets = []
        for request in widget_requests:
            widget = request["widget"]
            query = request["query"]
            mode = request["mode"]

            filters = _build_filters(query.get("filters"))
            results = search_engine.search(query["query"], mode=mode, filters=filters)
            sort_by = _normalize_sort_by(query.get("filters"))
            widget_sort = widget.get("sort_by")
            if isinstance(widget_sort, str) and widget_sort:
                sort_by = widget_sort

            sorted_list = sort_results(results.results, sort_by)
            widget_limit = widget.get("limit") if isinstance(widget.get("limit"), int) else 5
            trimmed = sorted_list[:widget_limit]

            response_results = [search_result_to_response(r) for r in trimmed]

            rendered_widgets.append(
                {
                    "id": widget.get("id"),
                    "title": widget.get("title") or query.get("name") or "Saved Query",
                    "query_id": query.get("id"),
                    "query": query.get("query"),
                    "mode": mode.value,
                    "sort_by": sort_by,
                    "results": response_results,
                    "total": results.total_count,
                    "search_time_ms": results.search_time_ms,
                }
            )

        return {
            "dashboard": dashboard,
            "widgets": rendered_widgets,
        }
    except HTTPException:
        raise
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


def _ensure_widgets(dashboard: dict[str, Any]) -> list[dict[str, Any]]:
    layout = dashboard.get("layout")
    if not isinstance(layout, dict):
        raise HTTPException(status_code=400, detail="Dashboard layout is invalid")
    widgets = layout.get("widgets")
    if not isinstance(widgets, list) or not widgets:
        raise HTTPException(status_code=400, detail="Dashboard layout is invalid")
    return widgets


def _parse_mode(mode_value: Any) -> SearchMode:
    mode_str = str(mode_value or "hybrid").lower()
    try:
        return SearchMode(mode_str)
    except Exception as exc:
        raise HTTPException(status_code=400, detail="Invalid search mode in saved query") from exc


def _build_filters(filters_value: Any) -> SearchFilters:
    filters = SearchFilters()
    if not isinstance(filters_value, dict):
        return filters

    project = filters_value.get("project")
    if isinstance(project, str) and project:
        filters.project_ids = [project]

    tool = filters_value.get("tool")
    if isinstance(tool, str) and tool:
        tool_value = tool.lower()
        if tool_value not in VALID_TOOL_NAMES:
            raise ValueError("Invalid tool filter in saved query")
        filters.tool = tool_value

    date = filters_value.get("date") if isinstance(filters_value.get("date"), str) else None
    date_from = filters_value.get("date_from") if isinstance(filters_value.get("date_from"), str) else None
    date_to = filters_value.get("date_to") if isinstance(filters_value.get("date_to"), str) else None
    filters.date_from, filters.date_to = parse_date_filter(date, date_from, date_to)

    return filters


def _normalize_sort_by(filters_value: Any) -> str:
    if isinstance(filters_value, dict):
        sort_by = filters_value.get("sort_by")
        if isinstance(sort_by, str) and sort_by:
            return sort_by
    return "relevance"


