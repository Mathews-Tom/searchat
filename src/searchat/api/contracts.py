"""Stable response contract serializers for API routes."""
from __future__ import annotations

from typing import Any

from searchat.api.models import SearchResultResponse
from searchat.api.utils import detect_source_from_path, detect_tool_from_path
from searchat.models import SearchResult


def serialize_search_result(result: SearchResult) -> SearchResultResponse:
    return SearchResultResponse(
        conversation_id=result.conversation_id,
        project_id=result.project_id,
        title=result.title,
        created_at=result.created_at.isoformat(),
        updated_at=result.updated_at.isoformat(),
        message_count=result.message_count,
        file_path=result.file_path,
        snippet=result.snippet,
        score=result.score,
        message_start_index=result.message_start_index,
        message_end_index=result.message_end_index,
        source=detect_source_from_path(result.file_path),
        tool=detect_tool_from_path(result.file_path),
    )


def serialize_search_payload(
    *,
    results: list[SearchResult],
    total: int,
    search_time_ms: float,
    limit: int,
    offset: int,
    highlight_terms: list[str] | None,
) -> dict[str, Any]:
    return {
        "results": [serialize_search_result(result) for result in results],
        "total": total,
        "search_time_ms": search_time_ms,
        "limit": limit,
        "offset": offset,
        "has_more": (offset + limit) < total,
        "highlight_terms": highlight_terms,
    }


def serialize_code_search_payload(
    *,
    results: list[dict[str, Any]],
    total: int,
    limit: int,
    offset: int,
) -> dict[str, Any]:
    return {
        "results": results,
        "total": total,
        "limit": limit,
        "offset": offset,
        "has_more": (offset + limit) < total,
    }


def serialize_projects_payload(projects: list[str]) -> list[str]:
    return projects


def serialize_conversations_payload(
    *,
    results: list[SearchResultResponse],
    total: int,
    search_time_ms: int,
) -> dict[str, Any]:
    return {
        "results": results,
        "total": total,
        "search_time_ms": search_time_ms,
    }


def serialize_search_suggestions_payload(
    *,
    query: str,
    suggestions: list[str],
) -> dict[str, Any]:
    return {
        "query": query,
        "suggestions": suggestions,
    }


def serialize_statistics_payload(stats: Any) -> dict[str, Any]:
    return {
        "total_conversations": stats.total_conversations,
        "total_messages": stats.total_messages,
        "avg_messages": stats.avg_messages,
        "total_projects": stats.total_projects,
        "earliest_date": stats.earliest_date,
        "latest_date": stats.latest_date,
    }


def serialize_readiness_payload(
    *,
    status: str,
    warmup_started_at: str | None,
    components: dict[str, str],
    watcher: str,
    errors: dict[str, str],
    retry_after_ms: int | None = None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "status": status,
        "warmup_started_at": warmup_started_at,
        "components": components,
        "watcher": watcher,
        "errors": errors,
    }
    if retry_after_ms is not None:
        payload["retry_after_ms"] = retry_after_ms
    return payload


def serialize_status_payload(
    *,
    server_started_at: str,
    warmup_started_at: str | None,
    components: dict[str, str],
    watcher: str,
    errors: dict[str, str],
    retrieval: dict[str, Any] | None,
) -> dict[str, Any]:
    return {
        "server_started_at": server_started_at,
        "warmup_started_at": warmup_started_at,
        "components": components,
        "watcher": watcher,
        "errors": errors,
        "retrieval": retrieval,
    }


def serialize_status_features_payload(
    *,
    analytics_enabled: bool,
    chat_enable_rag: bool,
    chat_enable_citations: bool,
    export_enable_ipynb: bool,
    export_enable_pdf: bool,
    export_enable_tech_docs: bool,
    dashboards_enabled: bool,
    snapshots_enabled: bool,
    retrieval: dict[str, Any] | None,
) -> dict[str, Any]:
    return {
        "analytics": {
            "enabled": analytics_enabled,
        },
        "chat": {
            "enable_rag": chat_enable_rag,
            "enable_citations": chat_enable_citations,
        },
        "export": {
            "enable_ipynb": export_enable_ipynb,
            "enable_pdf": export_enable_pdf,
            "enable_tech_docs": export_enable_tech_docs,
        },
        "dashboards": {
            "enabled": dashboards_enabled,
        },
        "snapshots": {
            "enabled": snapshots_enabled,
        },
        "retrieval": retrieval,
    }


def serialize_bookmark_payload(
    bookmark: dict[str, Any],
    *,
    conversation: dict[str, Any] | None = None,
) -> dict[str, Any]:
    payload = dict(bookmark)
    if conversation is None:
        return payload
    payload.update(
        title=conversation["title"],
        project_id=conversation["project_id"],
        message_count=conversation["message_count"],
        created_at=conversation["created_at"].isoformat(),
        updated_at=conversation["updated_at"].isoformat(),
    )
    return payload


def serialize_bookmarks_payload(bookmarks: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "total": len(bookmarks),
        "bookmarks": bookmarks,
    }


def serialize_bookmark_mutation_payload(bookmark: dict[str, Any]) -> dict[str, Any]:
    return {
        "success": True,
        "bookmark": bookmark,
    }


def serialize_bookmark_status_payload(bookmark: dict[str, Any] | None) -> dict[str, Any]:
    return {
        "is_bookmarked": bookmark is not None,
        "bookmark": bookmark,
    }


def serialize_success_message_payload(message: str) -> dict[str, Any]:
    return {
        "success": True,
        "message": message,
    }


def serialize_deleted_resource_payload(resource_id: str) -> dict[str, str]:
    return {
        "status": "deleted",
        "id": resource_id,
    }


def serialize_saved_queries_payload(queries: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "total": len(queries),
        "queries": queries,
    }


def serialize_saved_query_mutation_payload(query: dict[str, Any]) -> dict[str, Any]:
    return {
        "success": True,
        "query": query,
    }


def serialize_success_flag_payload() -> dict[str, Any]:
    return {"success": True}


def serialize_dashboards_payload(dashboards: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "total": len(dashboards),
        "dashboards": dashboards,
    }


def serialize_dashboard_payload(dashboard: dict[str, Any]) -> dict[str, Any]:
    return {"dashboard": dashboard}


def serialize_dashboard_mutation_payload(dashboard: dict[str, Any]) -> dict[str, Any]:
    return {
        "success": True,
        "dashboard": dashboard,
    }


def serialize_dashboard_render_payload(
    *,
    dashboard: dict[str, Any],
    widgets: list[dict[str, Any]],
) -> dict[str, Any]:
    return {
        "dashboard": dashboard,
        "widgets": widgets,
    }


def serialize_analytics_queries_payload(
    *,
    queries: list[dict[str, Any]],
    days: int,
) -> dict[str, Any]:
    return {
        "queries": queries,
        "days": days,
    }


def serialize_analytics_config_payload(
    *,
    enabled: bool,
    retention_days: int,
) -> dict[str, Any]:
    return {
        "enabled": enabled,
        "retention_days": retention_days,
    }


def serialize_analytics_trends_payload(
    *,
    days: int,
    points: list[dict[str, Any]],
) -> dict[str, Any]:
    return {
        "days": days,
        "points": points,
    }


def serialize_analytics_agent_comparison_payload(
    *,
    days: int,
    tools: list[dict[str, Any]],
) -> dict[str, Any]:
    return {
        "days": days,
        "tools": tools,
    }


def serialize_analytics_topics_payload(
    *,
    days: int,
    clusters: list[dict[str, Any]],
) -> dict[str, Any]:
    return {
        "days": days,
        "clusters": clusters,
    }


def serialize_backup_mutation_payload(
    *,
    backup: dict[str, Any],
    message: str,
) -> dict[str, Any]:
    return {
        "success": True,
        "backup": backup,
        "message": message,
    }


def serialize_backup_chain_payload(
    *,
    backup_name: str,
    chain: list[str],
    valid: bool = True,
    errors: list[str] | None = None,
) -> dict[str, Any]:
    return {
        "backup_name": backup_name,
        "chain": chain,
        "chain_length": len(chain),
        "valid": valid,
        "errors": [] if errors is None else errors,
    }


def serialize_backup_summary_fallback(
    *,
    name: str,
    chain_length: int,
    valid: bool,
    errors: list[str],
) -> dict[str, Any]:
    return {
        "name": name,
        "backup_mode": "full",
        "encrypted": False,
        "parent_name": None,
        "chain_length": chain_length,
        "snapshot_browsable": False,
        "has_manifest": False,
        "valid": valid,
        "errors": errors,
    }


def serialize_backups_payload(
    *,
    backups: list[dict[str, Any]],
    backup_directory: str,
) -> dict[str, Any]:
    return {
        "backups": backups,
        "total": len(backups),
        "backup_directory": backup_directory,
    }


def serialize_backup_restore_payload(
    *,
    restored_from: str,
    pre_restore_backup: dict[str, Any] | None = None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "success": True,
        "restored_from": restored_from,
        "message": f"Successfully restored from backup: {restored_from}",
    }
    if pre_restore_backup is not None:
        payload["pre_restore_backup"] = pre_restore_backup
    return payload


def serialize_backup_delete_payload(*, deleted: str) -> dict[str, Any]:
    return {
        "success": True,
        "deleted": deleted,
        "message": f"Backup deleted: {deleted}",
    }


def serialize_docs_summary_payload(
    *,
    title: str,
    format: str,
    generated_at: Any,
    content: str,
    citations: list[dict[str, Any]],
) -> dict[str, Any]:
    return {
        "title": title,
        "format": format,
        "generated_at": generated_at,
        "content": content,
        "citation_count": len(citations),
        "citations": citations,
    }


def serialize_agent_config_payload(
    *,
    format: str,
    content: str,
    pattern_count: int,
    project_filter: str | None,
) -> dict[str, Any]:
    return {
        "format": format,
        "content": content,
        "pattern_count": pattern_count,
        "project_filter": project_filter,
    }


def serialize_watcher_status_payload(
    *,
    running: bool,
    watched_directories: list[str],
    indexed_since_start: int,
    last_update: str | None,
) -> dict[str, Any]:
    return {
        "running": running,
        "watched_directories": watched_directories,
        "indexed_since_start": indexed_since_start,
        "last_update": last_update,
    }


def serialize_shutdown_blocked_payload(
    *,
    operation: str,
    files_total: int,
    elapsed_seconds: float,
    message: str,
) -> dict[str, Any]:
    return {
        "success": False,
        "indexing_in_progress": True,
        "operation": operation,
        "files_total": files_total,
        "elapsed_seconds": elapsed_seconds,
        "message": message,
    }


def serialize_shutdown_payload(*, forced: bool, message: str) -> dict[str, Any]:
    return {
        "success": True,
        "forced": forced,
        "message": message,
    }


def serialize_index_missing_payload(
    *,
    new_conversations: int,
    failed_conversations: int,
    empty_conversations: int,
    total_files: int,
    already_indexed: int,
    message: str,
    time_seconds: float | None = None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "success": True,
        "new_conversations": new_conversations,
        "failed_conversations": failed_conversations,
        "empty_conversations": empty_conversations,
        "total_files": total_files,
        "already_indexed": already_indexed,
        "message": message,
    }
    if time_seconds is not None:
        payload["time_seconds"] = time_seconds
    return payload


def serialize_delete_conversations_payload(
    *,
    deleted: int,
    removed_vectors: int,
    source_files_deleted: int,
) -> dict[str, Any]:
    return {
        "deleted": deleted,
        "removed_vectors": removed_vectors,
        "source_files_deleted": source_files_deleted,
    }


def serialize_resume_session_payload(
    *,
    tool: str,
    cwd: str | None,
    command: str,
    platform: str,
) -> dict[str, Any]:
    return {
        "success": True,
        "tool": tool,
        "cwd": cwd,
        "command": command,
        "platform": platform,
    }


def serialize_conversation_code_payload(
    *,
    conversation_id: str,
    title: str,
    code_blocks: list[dict[str, Any]],
) -> dict[str, Any]:
    return {
        "conversation_id": conversation_id,
        "title": title,
        "total_blocks": len(code_blocks),
        "code_blocks": code_blocks,
    }


def serialize_conversation_diff_payload(
    *,
    source_conversation_id: str,
    target_conversation_id: str,
    added: list[str],
    removed: list[str],
    unchanged: list[str],
) -> dict[str, Any]:
    return {
        "source_conversation_id": source_conversation_id,
        "target_conversation_id": target_conversation_id,
        "summary": {
            "added": len(added),
            "removed": len(removed),
            "unchanged": len(unchanged),
        },
        "added": added,
        "removed": removed,
        "unchanged": unchanged,
    }
