from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace

from searchat.expertise.models import ExpertiseRecord, ExpertiseType
from searchat.mcp.contracts import (
    serialize_agent_config_payload,
    serialize_conversation_payload,
    serialize_expertise_search_payload,
    serialize_history_answer_payload,
    serialize_patterns_payload,
    serialize_prime_expertise_payload,
    serialize_record_expertise_payload,
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


def _expertise_record() -> ExpertiseRecord:
    now = datetime(2026, 3, 16, tzinfo=timezone.utc)
    return ExpertiseRecord(
        type=ExpertiseType.CONVENTION,
        domain="python",
        content="Use explicit test fixtures.",
        project="project-a",
        confidence=0.9,
        created_at=now,
        last_validated=now,
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


def test_serialize_conversation_payload_preserves_stable_keys() -> None:
    payload = serialize_conversation_payload(
        {
            "conversation_id": "conv-123",
            "project_id": "project-a",
            "title": "Testing archive",
            "created_at": "2026-03-16T00:00:00+00:00",
            "updated_at": "2026-03-17T00:00:00+00:00",
            "message_count": 2,
            "file_path": "/tmp/conv-123.jsonl",
            "messages": [{"role": "user", "content": "hi"}],
            "ignored": "extra",
        }
    )

    assert list(payload) == [
        "conversation_id",
        "project_id",
        "title",
        "created_at",
        "updated_at",
        "message_count",
        "file_path",
        "messages",
    ]


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


def test_serialize_similar_conversations_payload_preserves_empty_envelope() -> None:
    payload = serialize_similar_conversations_payload(
        conversation_id="conv-123",
        title="Original conversation",
        similar_conversations=[],
    )

    assert payload == {
        "conversation_id": "conv-123",
        "title": "Original conversation",
        "similar_count": 0,
        "similar_conversations": [],
    }


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


def test_serialize_patterns_payload_preserves_pattern_shape() -> None:
    pattern = SimpleNamespace(
        name="Testing conventions",
        description="Start from failing tests.",
        confidence=0.8,
        evidence=[
            SimpleNamespace(
                conversation_id="conv-123",
                date="2026-03-16T00:00:00+00:00",
                snippet="Write the failing test first.",
            )
        ],
    )

    payload = serialize_patterns_payload([pattern])

    assert list(payload) == ["patterns", "total"]
    assert list(payload["patterns"][0]) == ["name", "description", "confidence", "evidence"]
    assert list(payload["patterns"][0]["evidence"][0]) == ["conversation_id", "date", "snippet"]


def test_serialize_prime_expertise_payload_preserves_top_level_shape() -> None:
    payload = serialize_prime_expertise_payload(
        {
            "expertise": [{"id": "exp-1"}],
            "token_count": 120,
            "domains_covered": ["python"],
            "records_total": 2,
            "records_included": 1,
            "records_filtered_inactive": 1,
        }
    )

    assert list(payload) == [
        "expertise",
        "token_count",
        "domains_covered",
        "records_total",
        "records_included",
        "records_filtered_inactive",
    ]


def test_serialize_record_expertise_payload_preserves_stable_keys() -> None:
    now = datetime(2026, 3, 16, tzinfo=timezone.utc)
    payload = serialize_record_expertise_payload(
        record_id="exp-1",
        action="created",
        record_type="convention",
        domain="python",
        content="Prefer pytest fixtures.",
        project="project-a",
        severity=None,
        created_at=now,
    )

    assert list(payload) == [
        "id",
        "action",
        "type",
        "domain",
        "content",
        "project",
        "severity",
        "created_at",
    ]


def test_serialize_expertise_search_payload_preserves_result_shape() -> None:
    payload = serialize_expertise_search_payload(
        records=[_expertise_record()],
        query="fixtures",
        domain="python",
        type_filter="convention",
    )

    assert list(payload) == ["results", "total", "query", "domain", "type"]
    assert list(payload["results"][0]) == [
        "id",
        "type",
        "domain",
        "content",
        "project",
        "confidence",
        "severity",
        "tags",
        "source_conversation_id",
        "source_agent",
        "name",
        "rationale",
        "resolution",
        "created_at",
        "last_validated",
        "validation_count",
        "is_active",
    ]


def test_serialize_agent_config_payload_preserves_stable_keys() -> None:
    payload = serialize_agent_config_payload(
        format="claude.md",
        content="# CLAUDE.md",
        pattern_count=3,
    )

    assert payload == {
        "format": "claude.md",
        "content": "# CLAUDE.md",
        "pattern_count": 3,
    }
