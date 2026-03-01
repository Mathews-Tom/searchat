"""Fragment router — serves HTML partials for HTMX-driven UI updates."""
from __future__ import annotations

import time
from typing import Any

from fastapi import APIRouter, Query, Request
from fastapi.responses import HTMLResponse
from starlette.responses import StreamingResponse

from searchat.api.templates import templates
import searchat.api.dependencies as deps
from searchat.expertise.models import ExpertiseQuery, ExpertiseType, ExpertiseSeverity
from searchat.models.domain import SearchFilters
from searchat.models.enums import SearchMode

router = APIRouter(prefix="/fragments", tags=["fragments"])


def _get_data_dir(config: Any) -> Any:
    """Resolve the data directory from config."""
    from pathlib import Path as _P
    return _P(config.paths.search_directory).expanduser()


def _domain_display_name(raw: str) -> str:
    """Extract a human-readable project name from a path-style domain identifier.

    '-Users-druk-WorkSpace-AetherForge-CAIRN' → 'CAIRN'
    'general' → 'general'
    """
    # Split on '-' (path separator used in project IDs) and take the last segment
    parts = raw.split("-")
    # Walk backwards past empty segments from leading dashes
    for part in reversed(parts):
        if part:
            return part
    return raw


def _safe_get(getter: Any) -> Any:
    """Call a dependency getter, returning None if services aren't ready."""
    try:
        return getter()
    except RuntimeError:
        return None


def _enrich_backups(svc: Any) -> list[dict[str, Any]]:
    """Convert BackupMetadata objects to template-friendly dicts."""
    from pathlib import Path as _Path

    raw = svc.list_backups()
    enriched: list[dict[str, Any]] = []
    for b in raw:
        entry = b.to_dict() if hasattr(b, "to_dict") else dict(b)
        backup_path = str(entry.get("backup_path", ""))
        name = _Path(backup_path).name if backup_path else entry.get("timestamp", "")
        entry.setdefault("name", name)
        entry.setdefault("created_at", entry.get("timestamp", ""))
        entry.setdefault("size_bytes", entry.get("total_size_bytes", 0))
        enriched.append(entry)
    return enriched


# ---------------------------------------------------------------------------
# Search
# ---------------------------------------------------------------------------

@router.get("/search-results", response_class=HTMLResponse)
async def search_results(
    request: Request,
    q: str = Query("", description="Search query"),
    mode: str = Query("hybrid", description="Search mode"),
    project: str = Query("", description="Project filter"),
    tool: str = Query("", description="Tool filter"),
    date: str = Query("", description="Date filter"),
    date_from: str = Query("", alias="dateFrom", description="Custom date from"),
    date_to: str = Query("", alias="dateTo", description="Custom date to"),
    sort_by: str = Query("relevance", alias="sortBy", description="Sort order"),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Results per page"),
    semantic_highlights: bool = Query(False),
    show_all: bool = Query(False, description="Show all conversations"),
) -> HTMLResponse:
    """Return search result cards as an HTML fragment."""
    engine = _safe_get(deps.get_search_engine)

    ctx: dict[str, Any] = {
        "results": [],
        "total": 0,
        "query": q,
        "page": page,
        "page_size": page_size,
        "total_pages": 0,
        "search_time_ms": 0,
        "mode": mode,
        "bookmarked_ids": set(),
        "error": None,
    }

    if engine is None:
        ctx["error"] = "Search engine not ready"
        return templates.TemplateResponse(request, "fragments/search-results.html", ctx)

    if q.strip() or show_all:
        start = time.perf_counter()
        search_q = q.strip() if q.strip() else "*"

        # Build typed filters
        filters = SearchFilters(
            project_ids=[project] if project else None,
            tool=tool or None,
        )
        search_mode = SearchMode(mode) if mode else SearchMode.HYBRID

        search_response = engine.search(
            query=search_q,
            mode=search_mode,
            filters=filters,
        )
        all_results = search_response.results
        ctx["total"] = search_response.total_count
        ctx["search_time_ms"] = round(search_response.search_time_ms, 1)

        # Manual pagination (SearchEngine returns all matches)
        offset = (page - 1) * page_size
        ctx["results"] = all_results[offset : offset + page_size]
        ctx["total_pages"] = (ctx["total"] + page_size - 1) // page_size

    bookmarks_svc = _safe_get(deps.get_bookmarks_service)
    if bookmarks_svc:
        all_bm = bookmarks_svc.list_bookmarks()
        ctx["bookmarked_ids"] = {b.get("conversation_id", b.get("id", "")) for b in all_bm}

    return templates.TemplateResponse(request, "fragments/search-results.html", ctx)


@router.get("/suggestions", response_class=HTMLResponse)
async def suggestions(
    request: Request,
    q: str = Query("", description="Partial query for suggestions"),
) -> HTMLResponse:
    """Return autocomplete suggestions as an HTML dropdown fragment."""
    engine = _safe_get(deps.get_search_engine)
    items: list[str] = []
    if engine and q.strip() and len(q.strip()) >= 2:
        try:
            items = engine.suggest(q.strip(), limit=8)
        except Exception:
            pass

    return templates.TemplateResponse(
        request, "fragments/suggestions-dropdown.html",
        {"suggestions": items, "query": q},
    )


@router.get("/project-summary", response_class=HTMLResponse)
async def project_summary(
    request: Request,
    project: str = Query("", description="Project to summarize"),
) -> HTMLResponse:
    """Return a project summary card fragment."""
    engine = _safe_get(deps.get_search_engine)
    summary = None
    if engine and project:
        try:
            summary = engine.get_project_summary(project)
        except Exception:
            pass

    return templates.TemplateResponse(
        request, "fragments/project-summary.html",
        {"summary": summary, "project": project},
    )


def _list_projects() -> list[str]:
    """Fetch project list from DuckDB store (mirrors /api/projects logic)."""
    try:
        search_dir, _snapshot_name = deps.resolve_dataset_search_dir(None)
        store = deps.get_duckdb_store_for(search_dir)
        if deps.projects_cache is None:
            deps.projects_cache = store.list_projects()
        return deps.projects_cache
    except (ValueError, RuntimeError):
        return []


@router.get("/project-options", response_class=HTMLResponse)
async def project_options(request: Request) -> HTMLResponse:
    """Return <option> tags for the project select dropdown."""
    return templates.TemplateResponse(
        request, "fragments/project-options.html",
        {"projects": _list_projects()},
    )


@router.get("/project-dropdown", response_class=HTMLResponse)
async def project_dropdown(request: Request) -> HTMLResponse:
    """Return filter dropdown buttons for the project filter chip."""
    return templates.TemplateResponse(
        request, "fragments/project-dropdown.html",
        {"projects": _list_projects()},
    )


@router.get("/manage-project-dropdown", response_class=HTMLResponse)
async def manage_project_dropdown(request: Request) -> HTMLResponse:
    """Return filter dropdown buttons for the manage page project filter."""
    store = _safe_get(deps.get_duckdb_store)
    projects: list[str] = []
    if store:
        projects = store.list_projects()
    return templates.TemplateResponse(
        request, "fragments/manage-project-dropdown.html",
        {"projects": projects},
    )


# ---------------------------------------------------------------------------
# Pagination
# ---------------------------------------------------------------------------

@router.get("/pagination", response_class=HTMLResponse)
async def pagination(
    request: Request,
    page: int = Query(1),
    total_pages: int = Query(1),
    q: str = Query(""),
    mode: str = Query("hybrid"),
    project: str = Query(""),
    tool: str = Query(""),
    date: str = Query(""),
    sort_by: str = Query("relevance", alias="sortBy"),
) -> HTMLResponse:
    """Return pagination buttons as an HTML fragment."""
    return templates.TemplateResponse(
        request, "fragments/pagination.html",
        {"page": page, "total_pages": total_pages, "q": q, "mode": mode,
         "project": project, "tool": tool, "date": date, "sort_by": sort_by},
    )


# ---------------------------------------------------------------------------
# Bookmarks
# ---------------------------------------------------------------------------

@router.get("/bookmarks-list", response_class=HTMLResponse)
async def bookmarks_list(request: Request) -> HTMLResponse:
    """Return the bookmarks list as an HTML fragment."""
    svc = _safe_get(deps.get_bookmarks_service)
    bookmarks = svc.list_bookmarks() if svc else []
    return templates.TemplateResponse(
        request, "fragments/bookmarks-list.html",
        {"bookmarks": bookmarks},
    )


@router.post("/bookmark-toggle/{conversation_id}", response_class=HTMLResponse)
async def bookmark_toggle(request: Request, conversation_id: str) -> HTMLResponse:
    """Toggle bookmark status and return the updated star button."""
    svc = _safe_get(deps.get_bookmarks_service)
    is_bookmarked = False
    if svc:
        current = svc.get_bookmark(conversation_id)
        if current:
            svc.remove_bookmark(conversation_id)
        else:
            svc.add_bookmark(conversation_id)
            is_bookmarked = True

    return templates.TemplateResponse(
        request, "fragments/bookmark-star.html",
        {"conversation_id": conversation_id, "is_bookmarked": is_bookmarked},
    )


# ---------------------------------------------------------------------------
# Backup
# ---------------------------------------------------------------------------

@router.get("/backup-list", response_class=HTMLResponse)
async def backup_list(request: Request) -> HTMLResponse:
    """Return the backup list panel as an HTML fragment."""
    svc = _safe_get(deps.get_backup_manager)
    backups = _enrich_backups(svc) if svc else []
    return templates.TemplateResponse(
        request, "fragments/backup-list.html",
        {"backups": backups},
    )


@router.post("/backup-create", response_class=HTMLResponse)
async def backup_create(request: Request) -> HTMLResponse:
    """Create a backup and return the status notification."""
    svc = _safe_get(deps.get_backup_manager)
    result = None
    error = None
    if svc:
        try:
            result = svc.create_backup()
        except Exception as e:
            error = str(e)
    else:
        error = "Backup service not available"

    return templates.TemplateResponse(
        request, "fragments/backup-status.html",
        {"result": result, "error": error},
    )


# ---------------------------------------------------------------------------
# Saved Queries
# ---------------------------------------------------------------------------

@router.get("/saved-queries-list", response_class=HTMLResponse)
async def saved_queries_list(request: Request) -> HTMLResponse:
    """Return saved queries items as an HTML fragment."""
    svc = _safe_get(deps.get_saved_queries_service)
    queries = svc.list_queries() if svc else []
    return templates.TemplateResponse(
        request, "fragments/saved-queries-list.html",
        {"queries": queries},
    )


@router.post("/saved-query", response_class=HTMLResponse)
async def saved_query_create(
    request: Request,
    q: str = Query("", description="Query text"),
    mode: str = Query("hybrid"),
    project: str = Query(""),
    tool: str = Query(""),
    date: str = Query(""),
    sort_by: str = Query("relevance", alias="sortBy"),
    query_name: str = Query("", description="Name for the saved query"),
    query_description: str = Query("", description="Description"),
) -> HTMLResponse:
    """Save a query and return updated list."""
    svc = _safe_get(deps.get_saved_queries_service)
    if svc and q.strip():
        svc.create_query({
            "name": query_name or q[:50],
            "query": q,
            "mode": mode,
            "filters": {
                "project": project or None,
                "tool": tool or None,
                "date": date or None,
                "sort_by": sort_by,
            },
            "description": query_description or None,
        })

    queries = svc.list_queries() if svc else []
    return templates.TemplateResponse(
        request, "fragments/saved-queries-list.html",
        {"queries": queries},
    )


@router.delete("/saved-query/{query_id}", response_class=HTMLResponse)
async def saved_query_delete(request: Request, query_id: str) -> HTMLResponse:
    """Delete a saved query and return updated list."""
    svc = _safe_get(deps.get_saved_queries_service)
    if svc:
        svc.delete_query(query_id)
    queries = svc.list_queries() if svc else []
    return templates.TemplateResponse(
        request, "fragments/saved-queries-list.html",
        {"queries": queries},
    )


# ---------------------------------------------------------------------------
# Index Missing
# ---------------------------------------------------------------------------

@router.post("/index-missing", response_class=HTMLResponse)
async def index_missing(request: Request) -> HTMLResponse:
    """Trigger index-missing and return result notification."""
    from searchat.api.routers.indexing import index_missing as _index_missing

    result = None
    error = None
    try:
        api_result = await _index_missing(snapshot=None)
        result = {
            "new_conversations": api_result.get("new_conversations", 0),
            "message": api_result.get("message", ""),
        }
    except Exception as e:
        error = str(e)

    return templates.TemplateResponse(
        request, "fragments/index-missing-result.html",
        {"result": result, "error": error},
    )


# ---------------------------------------------------------------------------
# Analytics
# ---------------------------------------------------------------------------

@router.get("/analytics-dashboard", response_class=HTMLResponse)
async def analytics_dashboard(
    request: Request,
    days: int = Query(30, ge=1, le=365),
) -> HTMLResponse:
    """Return the full analytics dashboard as an HTML fragment."""
    svc = _safe_get(deps.get_analytics_service)
    data: dict[str, Any] = {}
    if svc:
        try:
            data = {
                "summary": svc.get_stats_summary(days=days),
                "top_queries": svc.get_top_queries(limit=10, days=days),
                "dead_ends": svc.get_dead_end_queries(limit=10, days=days),
                "trends": svc.get_trends(days=days),
                "heatmap": svc.get_heatmap(days=days),
                "tools": svc.get_agent_comparison(days=days),
                "topics": svc.get_topic_clusters(days=days, k=8),
            }
        except Exception:
            pass

    return templates.TemplateResponse(
        request, "fragments/analytics-dashboard.html",
        {"analytics": data, "days": days},
    )


# ---------------------------------------------------------------------------
# Dashboards
# ---------------------------------------------------------------------------

@router.get("/dashboards-view", response_class=HTMLResponse)
async def dashboards_view(request: Request) -> HTMLResponse:
    """Return the dashboards view as an HTML fragment."""
    svc = _safe_get(deps.get_dashboards_service)
    dashboards = svc.list_dashboards() if svc else []
    return templates.TemplateResponse(
        request, "fragments/dashboards-view.html",
        {"dashboards": dashboards},
    )


# ---------------------------------------------------------------------------
# Expertise
# ---------------------------------------------------------------------------

@router.get("/expertise-view", response_class=HTMLResponse)
async def expertise_view(
    request: Request,
    domain: str = Query(""),
    type: str = Query("", alias="type"),
    severity: str = Query(""),
    active_only: bool = Query(True),
    q: str = Query(""),
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=100),
) -> HTMLResponse:
    """Return the expertise browser as an HTML fragment."""
    store = _safe_get(deps.get_expertise_store)
    records: list[Any] = []
    status_data: dict[str, Any] = {}
    total = 0
    if store:
        try:
            # Build status data from domain stats
            all_records = store.query(ExpertiseQuery(active_only=False, limit=10000))
            active = [r for r in all_records if r.is_active]
            domains_set = sorted({r.domain for r in all_records if r.domain})

            # Compute per-domain contradiction counts from KG store
            kg_store = _safe_get(deps.get_knowledge_graph_store)
            domain_contradiction_counts: dict[str, int] = {}
            if kg_store:
                try:
                    unresolved_edges = kg_store.get_contradictions(unresolved_only=True)
                    # Map record IDs to domains for counting
                    id_to_domain = {r.id: r.domain for r in all_records if r.domain}
                    for edge in unresolved_edges:
                        for rid in (edge.source_id, edge.target_id):
                            d_name = id_to_domain.get(rid, "")
                            if d_name:
                                domain_contradiction_counts[d_name] = domain_contradiction_counts.get(d_name, 0) + 1
                except Exception:
                    pass

            domain_stats = []
            for d in domains_set:
                raw = store.get_domain_stats(d)
                active_count = raw.get("active_records", 0)
                stale_count = raw.get("total_records", 0) - active_count
                c_count = domain_contradiction_counts.get(d, 0)
                if c_count > 5:
                    health = "critical"
                elif stale_count > active_count:
                    health = "warning"
                else:
                    health = "healthy"
                domain_stats.append({
                    "name": d,
                    "display_name": _domain_display_name(d),
                    "record_count": raw.get("total_records", 0),
                    "active_count": active_count,
                    "stale_count": stale_count,
                    "contradiction_count": c_count,
                    "health": health,
                    "avg_confidence": raw.get("avg_confidence", 0.0),
                })
            status_data = {
                "total_records": len(all_records),
                "active_records": len(active),
                "domains": domain_stats,
            }

            # Query filtered records
            parsed_type = ExpertiseType(type) if type else None
            parsed_severity = ExpertiseSeverity(severity) if severity else None
            query_obj = ExpertiseQuery(
                domain=domain or None,
                type=parsed_type,
                severity=parsed_severity,
                active_only=active_only,
                q=q or None,
                limit=page_size,
                offset=(page - 1) * page_size,
            )
            result_records = store.query(query_obj)
            records = [
                {
                    "id": r.id, "name": r.name, "type": r.type.value if r.type else "",
                    "domain": r.domain, "project": r.project,
                    "content": (r.content[:200] + "…") if len(r.content) > 200 else r.content,
                    "severity": r.severity.value if r.severity else None,
                    "tags": r.tags, "confidence": r.confidence, "is_active": r.is_active,
                    "example": r.example, "rationale": r.rationale,
                }
                for r in result_records
            ]
            total = store.count(query_obj)
        except Exception:
            pass

    return templates.TemplateResponse(
        request, "fragments/expertise-view.html",
        {
            "records": records,
            "status": status_data,
            "total": total,
            "domain": domain,
            "domain_display": _domain_display_name(domain) if domain else "",
            "type": type,
            "severity": severity,
            "active_only": active_only,
            "q": q,
            "page": page,
            "page_size": page_size,
        },
    )


# ---------------------------------------------------------------------------
# Contradictions (Knowledge Graph)
# ---------------------------------------------------------------------------

@router.get("/contradictions-view", response_class=HTMLResponse)
async def contradictions_view(
    request: Request,
    unresolved_only: bool = Query(True),
) -> HTMLResponse:
    """Return the knowledge graph contradictions view as an HTML fragment."""
    kg_store = _safe_get(deps.get_knowledge_graph_store)
    expertise_store = _safe_get(deps.get_expertise_store)
    contradiction_edges: list[Any] = []
    stats: dict[str, Any] = {}
    if kg_store:
        try:
            edges = kg_store.get_contradictions(unresolved_only=unresolved_only)
            contradiction_edges = [
                {
                    "edge_id": e.id, "record_id_a": e.source_id,
                    "record_id_b": e.target_id, "created_at": str(e.created_at),
                }
                for e in edges
            ]
            # Compute basic stats
            all_contradictions = kg_store.get_contradictions(unresolved_only=False)
            unresolved = kg_store.get_contradictions(unresolved_only=True)
            node_count = 0
            if expertise_store:
                all_records = expertise_store.query(ExpertiseQuery(active_only=False, limit=100000))
                node_count = len(all_records)
            health_score = max(0.0, 1.0 - (len(unresolved) / node_count if node_count > 0 else 0.0))
            stats = {
                "node_count": node_count,
                "edge_count": len(all_contradictions),
                "contradiction_count": len(all_contradictions),
                "unresolved_contradiction_count": len(unresolved),
                "health_score": round(health_score, 4),
            }
        except Exception:
            pass

    return templates.TemplateResponse(
        request, "fragments/contradictions-view.html",
        {"contradictions": contradiction_edges, "stats": stats, "unresolved_only": unresolved_only},
    )


# ---------------------------------------------------------------------------
# Similar Conversations
# ---------------------------------------------------------------------------

@router.get("/similar/{conversation_id}", response_class=HTMLResponse)
async def similar_conversations(
    request: Request,
    conversation_id: str,
) -> HTMLResponse:
    """Return similar conversations list as an HTML fragment."""
    from searchat.api.routers.conversations import get_similar_conversations as _get_similar

    similar: list[Any] = []
    try:
        result = await _get_similar(conversation_id, limit=5, snapshot=None)
        similar = result.get("similar_conversations", [])
    except Exception:
        pass

    return templates.TemplateResponse(
        request, "fragments/similar-conversations.html",
        {"similar": similar, "conversation_id": conversation_id},
    )


# ---------------------------------------------------------------------------
# Conversation View
# ---------------------------------------------------------------------------

@router.get("/conversation-view/{conversation_id}", response_class=HTMLResponse)
async def conversation_view(
    request: Request,
    conversation_id: str,
) -> HTMLResponse:
    """Return the full conversation with messages as an HTML fragment."""
    import re as _re
    from searchat.api.routers.conversations import get_conversation as _get_conv

    conversation = None
    error = None
    code_blocks: list[dict[str, Any]] = []
    try:
        conversation = await _get_conv(conversation_id, snapshot=None)
        # Extract code blocks from messages
        if conversation and hasattr(conversation, "messages"):
            pattern = r"```(\w*)\n(.*?)```"
            for msg in conversation.messages:
                matches = _re.findall(pattern, msg.content or "", _re.DOTALL)
                for lang, code in matches:
                    cleaned = code.strip()
                    if not cleaned:
                        continue
                    code_blocks.append({
                        "language": lang.strip() or "plaintext",
                        "code": cleaned,
                        "lines": len(cleaned.splitlines()),
                        "role": msg.role or "unknown",
                    })
    except Exception as e:
        error = str(e)

    return templates.TemplateResponse(
        request, "fragments/conversation-view.html",
        {
            "conversation": conversation,
            "code_blocks": code_blocks,
            "error": error,
            "conversation_id": conversation_id,
        },
    )


# ---------------------------------------------------------------------------
# Dataset Options
# ---------------------------------------------------------------------------

@router.get("/dataset-options", response_class=HTMLResponse)
async def dataset_options(request: Request) -> HTMLResponse:
    """Return <option> tags for the dataset/snapshot select."""
    svc = _safe_get(deps.get_backup_manager)
    backups = _enrich_backups(svc) if svc else []
    return templates.TemplateResponse(
        request, "fragments/dataset-options.html",
        {"backups": backups},
    )


# ---------------------------------------------------------------------------
# Server Shutdown
# ---------------------------------------------------------------------------

@router.post("/shutdown", response_class=HTMLResponse)
async def shutdown_server(request: Request) -> HTMLResponse:
    """Initiate graceful server shutdown and return a status fragment."""
    import os
    import signal
    import asyncio

    async def _delayed_shutdown() -> None:
        await asyncio.sleep(0.5)
        os.kill(os.getpid(), signal.SIGTERM)

    asyncio.get_event_loop().create_task(_delayed_shutdown())

    return HTMLResponse(
        '<div class="glass" style="padding: 24px; text-align: center;">'
        '<p style="color: hsl(var(--success));">Server shutting down gracefully&hellip;</p>'
        '<p style="color: hsl(var(--text-tertiary)); font-size: 13px;">You can close this tab.</p>'
        "</div>"
    )


# ---------------------------------------------------------------------------
# Rebuild Knowledge Graph & Expertise
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# Manage Conversations
# ---------------------------------------------------------------------------

@router.get("/manage-conversations", response_class=HTMLResponse)
async def manage_conversations(
    request: Request,
    project: str = Query("", description="Project filter"),
    tool: str = Query("", description="Tool filter"),
    date: str = Query("", description="Date filter"),
    date_from: str = Query("", alias="dateFrom", description="Custom date from"),
    date_to: str = Query("", alias="dateTo", description="Custom date to"),
    sort_by: str = Query("date_newest", alias="sortBy", description="Sort order"),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(50, ge=1, le=200, description="Results per page"),
) -> HTMLResponse:
    """Return conversation cards with checkboxes for the manage page."""
    from searchat.api.utils import detect_tool_from_path, parse_date_filter

    store = _safe_get(deps.get_duckdb_store)
    conversations: list[dict[str, Any]] = []
    total = 0

    if store:
        parsed_from, parsed_to = parse_date_filter(date, date_from or None, date_to or None)
        kwargs: dict[str, Any] = {
            "sort_by": sort_by,
            "project_id": project or None,
            "tool": tool or None,
            "date_from": parsed_from,
            "date_to": parsed_to,
            "limit": page_size,
            "offset": (page - 1) * page_size,
        }
        conversations = store.list_conversations(**kwargs)
        total = store.count_conversations(
            project_id=project or None,
            tool=tool or None,
            date_from=parsed_from,
            date_to=parsed_to,
        )

        # Enrich with tool badge
        for c in conversations:
            c["tool"] = detect_tool_from_path(c.get("file_path", ""))
            # Shorten file_path for display (replace home dir with ~)
            fp = c.get("file_path", "")
            import os
            home = os.path.expanduser("~")
            if fp.startswith(home):
                c["display_path"] = "~" + fp[len(home):]
            else:
                c["display_path"] = fp

    total_pages = (total + page_size - 1) // page_size if total > 0 else 0

    return templates.TemplateResponse(
        request, "fragments/manage-conversations.html",
        {
            "conversations": conversations,
            "total": total,
            "page": page,
            "page_size": page_size,
            "total_pages": total_pages,
            "project": project,
            "tool": tool,
            "date": date,
            "sort_by": sort_by,
        },
    )


@router.get("/conversation-preview/{conversation_id}", response_class=HTMLResponse)
async def conversation_preview(
    request: Request,
    conversation_id: str,
    max_messages: int = Query(10, ge=1, le=50, description="Max messages to preview"),
) -> HTMLResponse:
    """Return a lightweight conversation preview with truncated messages."""
    from searchat.api.routers.conversations import get_conversation as _get_conv

    conversation = None
    messages: list[dict[str, Any]] = []
    truncated = False
    remaining = 0
    error = None
    try:
        conversation = await _get_conv(conversation_id, snapshot=None)
        if conversation and hasattr(conversation, "messages"):
            all_msgs = conversation.messages or []
            total = len(all_msgs)
            truncated = total > max_messages
            remaining = total - max_messages if truncated else 0
            preview_msgs = all_msgs[:max_messages]
            # Truncate long message content for preview
            for msg in preview_msgs:
                content = msg.content or ""
                if len(content) > 500:
                    content = content[:500] + "…"
                messages.append({
                    "role": msg.role or "unknown",
                    "content": content,
                })
    except Exception as e:
        error = str(e)

    return templates.TemplateResponse(
        request, "fragments/conversation-preview.html",
        {
            "conversation": conversation,
            "messages": messages,
            "truncated": truncated,
            "remaining": remaining,
            "error": error,
            "conversation_id": conversation_id,
        },
    )


@router.post("/rebuild-knowledge-graph", response_class=HTMLResponse)
async def rebuild_knowledge_graph(request: Request) -> HTMLResponse:
    """Return the progress UI that connects to the KG rebuild SSE stream."""
    return templates.TemplateResponse(
        request, "fragments/rebuild-progress.html",
        {
            "stream_url": "/fragments/rebuild-knowledge-graph/stream",
            "done_url": "/fragments/contradictions-view",
        },
    )


@router.get("/rebuild-knowledge-graph/stream")
def rebuild_knowledge_graph_stream(request: Request) -> StreamingResponse:
    """SSE stream: rebuild knowledge graph with live progress."""
    import json as _json

    from searchat.expertise.embeddings import ExpertiseEmbeddingIndex
    from searchat.expertise.models import ExpertiseQuery as _EQ
    from searchat.knowledge_graph.detector import ContradictionDetector
    from searchat.knowledge_graph.models import EdgeType, KnowledgeEdge

    kg_store = _safe_get(deps.get_knowledge_graph_store)
    expertise_store = _safe_get(deps.get_expertise_store)

    def _sse(event: str, data: dict[str, Any]) -> str:
        return f"event: {event}\ndata: {_json.dumps(data)}\n\n"

    def generate():  # type: ignore[no-untyped-def]
        if not kg_store or not expertise_store:
            yield _sse("done", {"message": "Knowledge graph or expertise store not available."})
            return

        config = deps.get_config()
        records = expertise_store.query(_EQ(active_only=True, limit=10000))
        total = len(records)

        yield _sse("progress", {"phase": "Rebuilding embedding index", "current": 0, "total": total, "pct": -1})

        embedding_index = ExpertiseEmbeddingIndex(data_dir=_get_data_dir(config))
        embedding_index.rebuild(records)

        yield _sse("progress", {"phase": "Scanning for contradictions", "current": 0, "total": total, "pct": 0})

        detector = ContradictionDetector()
        new_contradictions = 0
        for i, record in enumerate(records):
            candidates = detector.check_record(record, expertise_store, embedding_index)
            for candidate in candidates:
                edge = KnowledgeEdge(
                    source_id=candidate.record_id_a,
                    target_id=candidate.record_id_b,
                    edge_type=EdgeType.CONTRADICTS,
                    metadata={
                        "similarity": candidate.similarity_score,
                        "nli_score": candidate.contradiction_score,
                    },
                )
                kg_store.create_edge(edge)
                new_contradictions += 1

            done_count = i + 1
            if done_count % 10 == 0 or done_count == total:
                pct = int(done_count / total * 100) if total else 100
                yield _sse("progress", {
                    "phase": "Scanning for contradictions",
                    "current": done_count,
                    "total": total,
                    "pct": pct,
                })

        msg = (
            f"<strong>Knowledge graph rebuilt.</strong> "
            f"Scanned {total} records, found {new_contradictions} new contradiction(s)."
        )
        yield _sse("done", {"message": msg})

    return StreamingResponse(generate(), media_type="text/event-stream")


@router.post("/rebuild-expertise-index", response_class=HTMLResponse)
async def rebuild_expertise_index(request: Request) -> HTMLResponse:
    """Return the progress UI that connects to the expertise rebuild SSE stream."""
    return templates.TemplateResponse(
        request, "fragments/rebuild-progress.html",
        {
            "stream_url": "/fragments/rebuild-expertise-index/stream",
            "done_url": "/fragments/expertise-view",
        },
    )


@router.get("/rebuild-expertise-index/stream")
def rebuild_expertise_index_stream(request: Request) -> StreamingResponse:
    """SSE stream: rebuild expertise embedding index with live progress."""
    import json as _json

    from searchat.expertise.embeddings import ExpertiseEmbeddingIndex
    from searchat.expertise.models import ExpertiseQuery as _EQ

    expertise_store = _safe_get(deps.get_expertise_store)

    def _sse(event: str, data: dict[str, Any]) -> str:
        return f"event: {event}\ndata: {_json.dumps(data)}\n\n"

    def generate():  # type: ignore[no-untyped-def]
        if not expertise_store:
            yield _sse("done", {"message": "Expertise store not available."})
            return

        config = deps.get_config()
        records = expertise_store.query(_EQ(active_only=True, limit=100000))
        total = len(records)

        yield _sse("progress", {"phase": f"Encoding {total} records", "current": 0, "total": total, "pct": -1})

        embedding_index = ExpertiseEmbeddingIndex(data_dir=_get_data_dir(config))
        embedding_index.rebuild(records)

        yield _sse("progress", {"phase": "Saving index", "current": total, "total": total, "pct": 100})

        msg = f"<strong>Expertise index rebuilt.</strong> Indexed {total} active records."
        yield _sse("done", {"message": msg})

    return StreamingResponse(generate(), media_type="text/event-stream")


# ---------------------------------------------------------------------------
# Contradiction resolution fragments
# ---------------------------------------------------------------------------


@router.get("/resolve-contradiction", response_class=HTMLResponse)
async def resolve_contradiction_form(
    request: Request,
    edge_id: str = Query(...),
    record_a: str = Query(...),
    record_b: str = Query(...),
) -> HTMLResponse:
    """Load the inline resolution form for a contradiction."""
    expertise_store = _safe_get(deps.get_expertise_store)
    if not expertise_store:
        return HTMLResponse(
            '<div style="padding: 8px; color: hsl(var(--danger)); font-size: 12px;">'
            "Expertise store not available.</div>"
        )

    rec_a = expertise_store.get(record_a)
    rec_b = expertise_store.get(record_b)

    if not rec_a or not rec_b:
        return HTMLResponse(
            '<div style="padding: 8px; color: hsl(var(--danger)); font-size: 12px;">'
            "Could not load one or both records.</div>"
        )

    return templates.TemplateResponse(
        request, "fragments/resolve-contradiction.html",
        {"edge_id": edge_id, "record_a": rec_a, "record_b": rec_b},
    )


@router.post("/apply-resolution", response_class=HTMLResponse)
async def apply_resolution(request: Request) -> HTMLResponse:
    """Apply a resolution strategy and return a success badge replacing the item."""
    form = await request.form()
    edge_id = str(form.get("edge_id", ""))
    strategy = str(form.get("strategy", ""))
    reason = str(form.get("reason", ""))
    winner_id = str(form.get("winner_id", ""))

    kg_store = _safe_get(deps.get_knowledge_graph_store)
    expertise_store = _safe_get(deps.get_expertise_store)

    if not kg_store or not expertise_store:
        return HTMLResponse(
            '<div class="glass" style="padding: 12px; color: hsl(var(--danger)); font-size: 12px;">'
            "Stores not available.</div>"
        )

    from searchat.knowledge_graph.models import EdgeType
    from searchat.knowledge_graph.resolver import ResolutionEngine

    edge = kg_store.get_edge(edge_id)
    if not edge or edge.edge_type != EdgeType.CONTRADICTS:
        return HTMLResponse(
            '<div class="glass" style="padding: 12px; color: hsl(var(--danger)); font-size: 12px;">'
            f"Edge not found or not a contradiction: {edge_id}</div>"
        )

    engine = ResolutionEngine(kg_store=kg_store, expertise_store=expertise_store)

    try:
        if strategy == "dismiss":
            engine.dismiss(edge_id, reason or "Dismissed via UI")
        elif strategy == "keep_both":
            engine.keep_both(edge_id, reason or "Kept both via UI")
        elif strategy == "supersede":
            engine.supersede(edge_id, winner_id)
        else:
            return HTMLResponse(
                '<div class="glass" style="padding: 12px; color: hsl(var(--danger)); font-size: 12px;">'
                f"Unsupported strategy: {strategy}</div>"
            )
    except Exception as exc:
        return HTMLResponse(
            '<div class="glass" style="padding: 12px; color: hsl(var(--danger)); font-size: 12px;">'
            f"Resolution failed: {exc}</div>"
        )

    return HTMLResponse(
        '<div class="contradiction-item glass" style="padding: 12px 16px; text-align: center;">'
        f'<span style="color: hsl(var(--success)); font-size: 13px;">'
        f'Resolved ({strategy})</span></div>'
    )
