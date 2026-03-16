from __future__ import annotations

from datetime import datetime
from typing import Any


def _serialize_datetime(value: datetime | str) -> str:
    return value if isinstance(value, str) else value.isoformat()


def serialize_similar_conversation(
    *,
    conversation_id: str,
    project_id: str,
    title: str,
    created_at: datetime | str,
    updated_at: datetime | str,
    message_count: int,
    tool: str,
    distance: float,
) -> dict[str, Any]:
    score = 1.0 / (1.0 + float(distance))
    return {
        "conversation_id": conversation_id,
        "project_id": project_id,
        "title": title,
        "created_at": _serialize_datetime(created_at),
        "updated_at": _serialize_datetime(updated_at),
        "message_count": message_count,
        "similarity_score": round(score, 3),
        "tool": tool,
    }


def serialize_similar_conversations_payload(
    *,
    conversation_id: str,
    title: str | None,
    similar_conversations: list[dict[str, Any]],
) -> dict[str, Any]:
    return {
        "conversation_id": conversation_id,
        "title": title,
        "similar_count": len(similar_conversations),
        "similar_conversations": similar_conversations,
    }
