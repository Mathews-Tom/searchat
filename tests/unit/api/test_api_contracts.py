from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace

from searchat.api.contracts import (
    serialize_projects_payload,
    serialize_readiness_payload,
    serialize_search_payload,
    serialize_status_features_payload,
    serialize_status_payload,
    serialize_statistics_payload,
)
from searchat.contracts.errors import (
    conversation_not_found_message,
    highlight_provider_required_message,
    invalid_highlight_provider_message,
    invalid_mcp_mode_message,
    invalid_mcp_tool_message,
    invalid_search_mode_message,
    invalid_tool_filter_message,
    mcp_offset_message,
    mcp_search_limit_message,
    mcp_similarity_limit_message,
    no_embeddings_for_conversation_message,
    snapshot_not_found_message,
)
from searchat.models import SearchResult


def _result() -> SearchResult:
    now = datetime(2026, 3, 16, tzinfo=timezone.utc)
    return SearchResult(
        conversation_id="conv-123",
        project_id="project-a",
        title="Contract result",
        created_at=now,
        updated_at=now,
        message_count=5,
        file_path="/home/user/.claude/conv-123.jsonl",
        score=0.8,
        snippet="Wave 4 API contract coverage.",
        message_start_index=1,
        message_end_index=2,
    )


def test_serialize_search_payload_preserves_stable_keys() -> None:
    payload = serialize_search_payload(
        results=[_result()],
        total=1,
        search_time_ms=4.0,
        limit=20,
        offset=0,
        highlight_terms=None,
    )

    assert list(payload) == [
        "results",
        "total",
        "search_time_ms",
        "limit",
        "offset",
        "has_more",
        "highlight_terms",
    ]
    assert list(payload["results"][0].model_dump()) == [
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
        "source",
        "tool",
    ]


def test_serialize_projects_payload_preserves_list_shape() -> None:
    payload = serialize_projects_payload(["proj-a", "proj-b"])
    assert payload == ["proj-a", "proj-b"]


def test_serialize_statistics_payload_preserves_stable_keys() -> None:
    stats = SimpleNamespace(
        total_conversations=10,
        total_messages=100,
        avg_messages=10.0,
        total_projects=2,
        earliest_date="2025-01-01",
        latest_date="2025-06-01",
    )

    payload = serialize_statistics_payload(stats)

    assert list(payload) == [
        "total_conversations",
        "total_messages",
        "avg_messages",
        "total_projects",
        "earliest_date",
        "latest_date",
    ]


def test_serialize_readiness_payload_preserves_control_plane_keys() -> None:
    payload = serialize_readiness_payload(
        status="warming",
        warmup_started_at="2026-03-16T00:00:00+00:00",
        components={"metadata": "loading"},
        watcher="disabled",
        errors={},
        retry_after_ms=500,
    )

    assert list(payload) == [
        "status",
        "warmup_started_at",
        "components",
        "watcher",
        "errors",
        "retry_after_ms",
    ]


def test_serialize_status_payload_preserves_status_keys() -> None:
    payload = serialize_status_payload(
        server_started_at="2026-03-16T00:00:00+00:00",
        warmup_started_at=None,
        components={"services": "ready"},
        watcher="running",
        errors={},
        retrieval={"semantic_available": True},
    )

    assert list(payload) == [
        "server_started_at",
        "warmup_started_at",
        "components",
        "watcher",
        "errors",
        "retrieval",
    ]


def test_serialize_status_features_payload_preserves_feature_groups() -> None:
    payload = serialize_status_features_payload(
        analytics_enabled=True,
        chat_enable_rag=True,
        chat_enable_citations=False,
        export_enable_ipynb=False,
        export_enable_pdf=True,
        export_enable_tech_docs=False,
        dashboards_enabled=True,
        snapshots_enabled=True,
        retrieval={"semantic_available": False},
    )

    assert list(payload) == [
        "analytics",
        "chat",
        "export",
        "dashboards",
        "snapshots",
        "retrieval",
    ]


def test_shared_error_contract_messages_are_stable() -> None:
    assert invalid_search_mode_message() == "Invalid search mode"
    assert invalid_mcp_mode_message() == "Invalid mode; expected: hybrid, semantic, keyword"
    assert invalid_tool_filter_message() == "Invalid tool filter"
    assert invalid_mcp_tool_message().startswith("Invalid tool; expected one of:")
    assert highlight_provider_required_message() == "Highlight provider is required"
    assert invalid_highlight_provider_message() == "Invalid highlight provider"
    assert snapshot_not_found_message() == "Snapshot not found"
    assert conversation_not_found_message("conv-123") == "Conversation not found: conv-123"
    assert no_embeddings_for_conversation_message() == "No embeddings found for this conversation"
    assert mcp_search_limit_message() == "limit must be between 1 and 100"
    assert mcp_similarity_limit_message() == "limit must be between 1 and 20"
    assert mcp_offset_message() == "offset must be >= 0"
