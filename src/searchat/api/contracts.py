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


def serialize_projects_payload(projects: list[str]) -> list[str]:
    return projects


def serialize_statistics_payload(stats: Any) -> dict[str, Any]:
    return {
        "total_conversations": stats.total_conversations,
        "total_messages": stats.total_messages,
        "avg_messages": stats.avg_messages,
        "total_projects": stats.total_projects,
        "earliest_date": stats.earliest_date,
        "latest_date": stats.latest_date,
    }
