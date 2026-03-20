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


def serialize_conversation_payload(record: dict[str, Any]) -> dict[str, Any]:
    return {
        "conversation_id": record.get("conversation_id"),
        "project_id": record.get("project_id"),
        "title": record.get("title"),
        "created_at": record.get("created_at"),
        "updated_at": record.get("updated_at"),
        "message_count": record.get("message_count"),
        "file_path": record.get("file_path"),
        "messages": record.get("messages"),
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


def serialize_patterns_payload(patterns: list[Any]) -> dict[str, Any]:
    return {
        "patterns": [
            {
                "name": pattern.name,
                "description": pattern.description,
                "confidence": pattern.confidence,
                "evidence": [
                    {
                        "conversation_id": evidence.conversation_id,
                        "date": evidence.date,
                        "snippet": evidence.snippet,
                    }
                    for evidence in pattern.evidence
                ],
            }
            for pattern in patterns
        ],
        "total": len(patterns),
    }


def serialize_prime_expertise_payload(payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "expertise": payload["expertise"],
        "token_count": payload["token_count"],
        "domains_covered": payload["domains_covered"],
        "records_total": payload["records_total"],
        "records_included": payload["records_included"],
        "records_filtered_inactive": payload["records_filtered_inactive"],
    }


def serialize_record_expertise_payload(
    *,
    record_id: str,
    action: str,
    record_type: str,
    domain: str,
    content: str,
    project: str | None,
    severity: str | None,
    created_at: Any,
) -> dict[str, Any]:
    return {
        "id": record_id,
        "action": action,
        "type": record_type,
        "domain": domain,
        "content": content,
        "project": project,
        "severity": severity,
        "created_at": created_at,
    }


def serialize_expertise_search_payload(
    *,
    records: list[Any],
    query: str,
    domain: str | None,
    type_filter: str | None,
) -> dict[str, Any]:
    return {
        "results": [
            {
                "id": record.id,
                "type": record.type.value,
                "domain": record.domain,
                "content": record.content,
                "project": record.project,
                "confidence": record.confidence,
                "severity": record.severity.value if record.severity else None,
                "tags": record.tags,
                "source_conversation_id": record.source_conversation_id,
                "source_agent": record.source_agent,
                "name": record.name,
                "rationale": record.rationale,
                "resolution": record.resolution,
                "created_at": record.created_at,
                "last_validated": record.last_validated,
                "validation_count": record.validation_count,
                "is_active": record.is_active,
            }
            for record in records
        ],
        "total": len(records),
        "query": query,
        "domain": domain,
        "type": type_filter,
    }


def serialize_agent_config_payload(
    *,
    format: str,
    content: str,
    pattern_count: int,
) -> dict[str, Any]:
    return {
        "format": format,
        "content": content,
        "pattern_count": pattern_count,
    }
