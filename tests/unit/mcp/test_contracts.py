from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace

from searchat.mcp.contracts import (
    serialize_history_answer_payload,
    serialize_search_payload,
    serialize_similar_conversation,
    serialize_similar_conversations_payload,
    serialize_statistics_payload,
)
from searchat.models import SearchResult, SearchResults


def _search_result() -> SearchResult:
    now = datetime(2026, 3, 16, tzinfo=timezone.utc)
    return SearchResult(
        conversation_id="conv-123",
        project_id="project-a",
        title="Testing archive",
        created_at=now,
        updated_at=now,
        message_count=7,
        file_path="/tmp/conv-123.jsonl",
        score=0.91,
        snippet="Investigate the failing test first.",
        message_start_index=1,
        message_end_index=3,
    )


def test_serialize_search_payload_preserves_stable_keys() -> None:
    payload = serialize_search_payload(
        SearchResults(
            results=[_search_result()],
            total_count=1,
            search_time_ms=4.2,
            mode_used="hybrid",
        ),
        limit=10,
        offset=0,
    )

    assert list(payload) == ["results", "total", "limit", "offset", "mode_used", "search_time_ms"]
    assert list(payload["results"][0]) == [
        "conversation_id",
        "project_id",
        "title",
        "created_at",
        "updated_at",
        "message_count",
        "file_path",
        "snippet",
        "score",
        "message_start_index",
        "message_end_index",
    ]


def test_serialize_statistics_payload_preserves_summary_keys() -> None:
    stats = SimpleNamespace(
        total_conversations=10,
        total_messages=100,
        avg_messages=10.0,
        total_projects=2,
        earliest_date="2025-01-01",
        latest_date="2025-06-01",
    )

    payload = serialize_statistics_payload(stats)

    assert payload == {
        "total_conversations": 10,
        "total_messages": 100,
        "avg_messages": 10.0,
        "total_projects": 2,
        "earliest_date": "2025-01-01",
        "latest_date": "2025-06-01",
    }


def test_serialize_similar_conversations_payload_preserves_core_fields() -> None:
    similar = serialize_similar_conversation(
        conversation_id="conv-456",
        project_id="project-a",
        title="Similar conversation",
        created_at="2026-01-20T10:00:00+00:00",
        updated_at="2026-01-21T10:00:00+00:00",
        message_count=4,
        file_path="/tmp/conv-456.jsonl",
        distance=0.25,
    )
    payload = serialize_similar_conversations_payload(
        conversation_id="conv-123",
        title="Original conversation",
        similar_conversations=[similar],
    )

    assert list(payload) == ["conversation_id", "title", "similar_count", "similar_conversations"]
    assert list(payload["similar_conversations"][0]) == [
        "conversation_id",
        "project_id",
        "title",
        "created_at",
        "updated_at",
        "message_count",
        "similarity_score",
        "tool",
    ]


def test_serialize_history_answer_payload_preserves_source_shape() -> None:
    payload = serialize_history_answer_payload(answer="fallback", sources=[_search_result()])

    assert payload["answer"] == "fallback"
    assert list(payload["sources"][0]) == [
        "conversation_id",
        "project_id",
        "title",
        "score",
        "snippet",
        "message_start_index",
        "message_end_index",
        "tool",
    ]
