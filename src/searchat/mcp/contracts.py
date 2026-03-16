from __future__ import annotations

from types import SimpleNamespace
from typing import Any

from searchat.api.utils import detect_tool_from_path
from searchat.contracts.similarity import (
    serialize_similar_conversation as serialize_shared_similar_conversation,
    serialize_similar_conversations_payload,
)
from searchat.models import SearchResult, SearchResults


def serialize_search_result(result: SearchResult) -> dict[str, Any]:
    return {
        "conversation_id": result.conversation_id,
        "project_id": result.project_id,
        "title": result.title,
        "created_at": result.created_at,
        "updated_at": result.updated_at,
        "message_count": result.message_count,
        "file_path": result.file_path,
        "snippet": result.snippet,
        "score": result.score,
        "message_start_index": result.message_start_index,
        "message_end_index": result.message_end_index,
    }


def serialize_search_payload(
    results: SearchResults,
    *,
    limit: int,
    offset: int,
) -> dict[str, Any]:
    sliced = results.results[offset : offset + limit]
    return {
        "results": [serialize_search_result(result) for result in sliced],
        "total": len(results.results),
        "limit": limit,
        "offset": offset,
        "mode_used": results.mode_used,
        "search_time_ms": results.search_time_ms,
    }


def serialize_projects_payload(projects: list[str]) -> dict[str, Any]:
    return {"projects": projects}


def serialize_statistics_payload(stats: SimpleNamespace) -> dict[str, Any]:
    return {
        "total_conversations": stats.total_conversations,
        "total_messages": stats.total_messages,
        "avg_messages": stats.avg_messages,
        "total_projects": stats.total_projects,
        "earliest_date": stats.earliest_date,
        "latest_date": stats.latest_date,
    }


def serialize_similar_conversation(
    *,
    conversation_id: str,
    project_id: str,
    title: str,
    created_at,
    updated_at,
    message_count: int,
    file_path: str,
    distance: float,
) -> dict[str, Any]:
    return serialize_shared_similar_conversation(
        conversation_id=conversation_id,
        project_id=project_id,
        title=title,
        created_at=created_at,
        updated_at=updated_at,
        message_count=message_count,
        tool=detect_tool_from_path(file_path),
        distance=distance,
    )


def serialize_history_source(result: SearchResult) -> dict[str, Any]:
    return {
        "conversation_id": result.conversation_id,
        "project_id": result.project_id,
        "title": result.title,
        "score": result.score,
        "snippet": result.snippet,
        "message_start_index": result.message_start_index,
        "message_end_index": result.message_end_index,
        "tool": detect_tool_from_path(result.file_path),
    }


def serialize_history_answer_payload(
    *,
    answer: str,
    sources: list[SearchResult] | None = None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {"answer": answer}
    if sources is not None:
        payload["sources"] = [serialize_history_source(result) for result in sources]
    return payload
