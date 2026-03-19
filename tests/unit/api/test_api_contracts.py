from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace

from searchat.api.contracts import (
    serialize_backup_chain_payload,
    serialize_backup_delete_payload,
    serialize_backup_mutation_payload,
    serialize_backup_restore_payload,
    serialize_backup_summary_fallback,
    serialize_backups_payload,
    serialize_conversation_code_payload,
    serialize_conversation_diff_payload,
    serialize_docs_summary_payload,
    serialize_agent_config_payload,
    serialize_index_missing_payload,
    serialize_resume_session_payload,
    serialize_shutdown_blocked_payload,
    serialize_shutdown_payload,
    serialize_watcher_status_payload,
    serialize_analytics_agent_comparison_payload,
    serialize_analytics_config_payload,
    serialize_analytics_queries_payload,
    serialize_analytics_topics_payload,
    serialize_analytics_trends_payload,
    serialize_dashboard_mutation_payload,
    serialize_dashboard_payload,
    serialize_dashboard_render_payload,
    serialize_dashboards_payload,
    serialize_bookmark_mutation_payload,
    serialize_bookmark_payload,
    serialize_bookmark_status_payload,
    serialize_bookmarks_payload,
    serialize_projects_payload,
    serialize_readiness_payload,
    serialize_saved_queries_payload,
    serialize_saved_query_mutation_payload,
    serialize_search_payload,
    serialize_success_flag_payload,
    serialize_success_message_payload,
    serialize_status_features_payload,
    serialize_status_payload,
    serialize_statistics_payload,
)
from searchat.contracts.errors import (
    analytics_active_dataset_only_message,
    backup_chain_resolution_unavailable_message,
    backup_not_found_message,
    backup_operations_disabled_message,
    backup_summary_unavailable_message,
    backup_validation_unavailable_message,
    dashboard_not_found_message,
    dashboard_layout_columns_invalid_message,
    dashboard_layout_required_message,
    dashboard_layout_widgets_required_message,
    dashboard_missing_created_at_message,
    dashboard_name_required_message,
    dashboard_queries_invalid_message,
    dashboard_queries_missing_widget_ids_message,
    dashboard_refresh_interval_invalid_message,
    dashboard_widget_id_invalid_message,
    dashboard_widget_layout_invalid_message,
    dashboard_widget_limit_invalid_message,
    dashboard_widget_object_required_message,
    dashboard_widget_query_id_required_message,
    dashboard_widget_sort_by_invalid_message,
    dashboard_widget_title_invalid_message,
    dashboards_disabled_message,
    dashboards_file_invalid_message,
    bookmark_notes_updated_message,
    bookmark_not_found_message,
    bookmark_removed_message,
    bulk_export_no_ids_message,
    bulk_export_too_many_message,
    conversation_internal_server_error_message,
    conversation_encoding_error_message,
    conversation_file_missing_message,
    conversation_file_missing_with_record_message,
    conversation_invalid_json_message,
    conversation_not_found_in_index_message,
    conversation_not_found_in_snapshot_message,
    conversation_not_found_message_simple,
    conversation_not_found_message,
    export_disabled_message,
    highlight_provider_required_message,
    invalid_highlight_provider_message,
    invalid_model_provider_message,
    invalid_export_format_message,
    invalid_mcp_mode_message,
    invalid_mcp_tool_message,
    invalid_search_mode_message,
    invalid_saved_query_mode_message,
    invalid_saved_query_tool_filter_message,
    invalid_target_conversation_id_message,
    invalid_tool_filter_message,
    indexing_snapshot_disabled_message,
    internal_server_error_message,
    mcp_offset_message,
    mcp_search_limit_message,
    mcp_similarity_limit_message,
    no_embeddings_for_conversation_message,
    no_similar_conversation_found_message,
    reindex_blocked_message,
    retrieval_capability_inspection_failed_message,
    resume_command_not_found_message,
    resume_snapshot_disabled_message,
    saved_queries_file_invalid_message,
    saved_query_filters_required_message,
    saved_query_missing_created_at_message,
    saved_query_mode_required_message,
    saved_query_name_required_message,
    saved_query_not_found_message,
    saved_query_invalid_message,
    saved_query_missing_message,
    saved_query_text_required_message,
    saved_query_use_count_invalid_message,
    snapshot_not_found_message,
    target_conversation_not_found_message,
    tech_docs_disabled_message,
    unknown_conversation_format_message,
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


def test_serialize_bookmark_payloads_preserve_saved_state_shapes() -> None:
    bookmark = {
        "conversation_id": "conv-123",
        "added_at": "2026-03-16T00:00:00+00:00",
        "notes": "important",
    }
    conversation = {
        "title": "Contract result",
        "project_id": "project-a",
        "message_count": 5,
        "created_at": datetime(2026, 3, 16, tzinfo=timezone.utc),
        "updated_at": datetime(2026, 3, 17, tzinfo=timezone.utc),
    }

    enriched = serialize_bookmark_payload(bookmark, conversation=conversation)
    assert list(enriched) == [
        "conversation_id",
        "added_at",
        "notes",
        "title",
        "project_id",
        "message_count",
        "created_at",
        "updated_at",
    ]

    assert serialize_bookmarks_payload([enriched]) == {
        "total": 1,
        "bookmarks": [enriched],
    }
    assert serialize_bookmark_mutation_payload(bookmark) == {
        "success": True,
        "bookmark": bookmark,
    }
    assert serialize_bookmark_status_payload(bookmark) == {
        "is_bookmarked": True,
        "bookmark": bookmark,
    }
    assert serialize_bookmark_status_payload(None) == {
        "is_bookmarked": False,
        "bookmark": None,
    }


def test_serialize_saved_query_payloads_preserve_saved_query_shapes() -> None:
    query = {
        "id": "q-123",
        "name": "Release Checks",
        "query": "deployment",
    }

    assert serialize_saved_queries_payload([query]) == {
        "total": 1,
        "queries": [query],
    }
    assert serialize_saved_query_mutation_payload(query) == {
        "success": True,
        "query": query,
    }
    assert serialize_success_message_payload("ok") == {
        "success": True,
        "message": "ok",
    }
    assert serialize_success_flag_payload() == {"success": True}


def test_serialize_dashboard_payloads_preserve_dashboard_shapes() -> None:
    dashboard = {
        "id": "d-123",
        "name": "Daily Ops",
        "layout": {"widgets": [{"query_id": "q-1"}]},
    }
    widget = {
        "id": "w-1",
        "results": [],
    }

    assert serialize_dashboards_payload([dashboard]) == {
        "total": 1,
        "dashboards": [dashboard],
    }
    assert serialize_dashboard_payload(dashboard) == {"dashboard": dashboard}
    assert serialize_dashboard_mutation_payload(dashboard) == {
        "success": True,
        "dashboard": dashboard,
    }
    assert serialize_dashboard_render_payload(dashboard=dashboard, widgets=[widget]) == {
        "dashboard": dashboard,
        "widgets": [widget],
    }


def test_serialize_analytics_payloads_preserve_shapes() -> None:
    query = {"query": "python", "search_count": 3}
    point = {"day": "2026-01-01", "searches": 3}
    tool = {"tool_filter": "all", "searches": 10}
    cluster = {"cluster_id": 0, "searches": 10}

    assert serialize_analytics_queries_payload(queries=[query], days=7) == {
        "queries": [query],
        "days": 7,
    }
    assert serialize_analytics_config_payload(enabled=True, retention_days=14) == {
        "enabled": True,
        "retention_days": 14,
    }
    assert serialize_analytics_trends_payload(days=30, points=[point]) == {
        "days": 30,
        "points": [point],
    }
    assert serialize_analytics_agent_comparison_payload(days=30, tools=[tool]) == {
        "days": 30,
        "tools": [tool],
    }
    assert serialize_analytics_topics_payload(days=30, clusters=[cluster]) == {
        "days": 30,
        "clusters": [cluster],
    }


def test_serialize_backup_payloads_preserve_shapes() -> None:
    backup = {
        "backup_path": "/backups/backup_20250120_100000",
        "timestamp": "20250120_100000",
        "file_count": 5,
        "total_size_mb": 10.5,
    }

    assert serialize_backup_mutation_payload(
        backup=backup,
        message="Backup created: backup_20250120_100000",
    ) == {
        "success": True,
        "backup": backup,
        "message": "Backup created: backup_20250120_100000",
    }
    assert serialize_backup_chain_payload(
        backup_name="backup_20250120_100000",
        chain=["backup_20250120_090000", "backup_20250120_100000"],
        valid=False,
        errors=["missing parent"],
    ) == {
        "backup_name": "backup_20250120_100000",
        "chain": ["backup_20250120_090000", "backup_20250120_100000"],
        "chain_length": 2,
        "valid": False,
        "errors": ["missing parent"],
    }

    summary = serialize_backup_summary_fallback(
        name="backup_20250120_100000",
        chain_length=1,
        valid=False,
        errors=[],
    )
    assert list(summary) == [
        "name",
        "backup_mode",
        "encrypted",
        "parent_name",
        "chain_length",
        "snapshot_browsable",
        "has_manifest",
        "valid",
        "errors",
    ]
    assert serialize_backups_payload(backups=[summary], backup_directory="/backups") == {
        "backups": [summary],
        "total": 1,
        "backup_directory": "/backups",
    }
    assert serialize_backup_restore_payload(restored_from="backup_20250120_100000") == {
        "success": True,
        "restored_from": "backup_20250120_100000",
        "message": "Successfully restored from backup: backup_20250120_100000",
    }
    assert serialize_backup_delete_payload(deleted="backup_20250120_100000") == {
        "success": True,
        "deleted": "backup_20250120_100000",
        "message": "Backup deleted: backup_20250120_100000",
    }


def test_serialize_docs_and_agent_config_payloads_preserve_shapes() -> None:
    citation = {
        "conversation_id": "conv-1",
        "title": "T",
        "project_id": "p",
        "date": "2026-03-16T00:00:00+00:00",
    }
    docs_payload = serialize_docs_summary_payload(
        title="My Doc",
        format="markdown",
        generated_at="2026-03-16T00:00:00+00:00",
        content="# My Doc",
        citations=[citation],
    )
    assert list(docs_payload) == [
        "title",
        "format",
        "generated_at",
        "content",
        "citation_count",
        "citations",
    ]
    assert docs_payload["citation_count"] == 1

    agent_payload = serialize_agent_config_payload(
        format="claude.md",
        content="# Project",
        pattern_count=2,
        project_filter="searchat",
    )
    assert agent_payload == {
        "format": "claude.md",
        "content": "# Project",
        "pattern_count": 2,
        "project_filter": "searchat",
    }


def test_serialize_admin_and_indexing_payloads_preserve_shapes() -> None:
    watcher_payload = serialize_watcher_status_payload(
        running=True,
        watched_directories=["/tmp/a", "/tmp/b"],
        indexed_since_start=5,
        last_update="2026-03-16T00:00:00+00:00",
    )
    assert list(watcher_payload) == [
        "running",
        "watched_directories",
        "indexed_since_start",
        "last_update",
    ]

    blocked_payload = serialize_shutdown_blocked_payload(
        operation="manual_index",
        files_total=100,
        elapsed_seconds=5.5,
        message="blocked",
    )
    assert list(blocked_payload) == [
        "success",
        "indexing_in_progress",
        "operation",
        "files_total",
        "elapsed_seconds",
        "message",
    ]
    assert blocked_payload["success"] is False

    assert serialize_shutdown_payload(forced=False, message="graceful") == {
        "success": True,
        "forced": False,
        "message": "graceful",
    }

    index_payload = serialize_index_missing_payload(
        new_conversations=2,
        failed_conversations=1,
        empty_conversations=0,
        total_files=5,
        already_indexed=3,
        time_seconds=1.25,
        message="done",
    )
    assert list(index_payload) == [
        "success",
        "new_conversations",
        "failed_conversations",
        "empty_conversations",
        "total_files",
        "already_indexed",
        "message",
        "time_seconds",
    ]

    assert serialize_resume_session_payload(
        tool="claude",
        cwd="/tmp/project",
        command="claude --resume conv-1",
        platform="darwin",
    ) == {
        "success": True,
        "tool": "claude",
        "cwd": "/tmp/project",
        "command": "claude --resume conv-1",
        "platform": "darwin",
    }

    code_payload = serialize_conversation_code_payload(
        conversation_id="conv-1",
        title="Code blocks",
        code_blocks=[{"message_index": 0, "language": "python", "code": "print('hi')"}],
    )
    assert list(code_payload) == ["conversation_id", "title", "total_blocks", "code_blocks"]
    assert code_payload["total_blocks"] == 1

    diff_payload = serialize_conversation_diff_payload(
        source_conversation_id="conv-1",
        target_conversation_id="conv-2",
        added=["new line"],
        removed=["old line"],
        unchanged=["same line"],
    )
    assert list(diff_payload) == [
        "source_conversation_id",
        "target_conversation_id",
        "summary",
        "added",
        "removed",
        "unchanged",
    ]
    assert diff_payload["summary"] == {"added": 1, "removed": 1, "unchanged": 1}


def test_shared_error_contract_messages_are_stable() -> None:
    assert invalid_search_mode_message() == "Invalid search mode"
    assert invalid_mcp_mode_message() == "Invalid mode; expected: hybrid, semantic, keyword"
    assert invalid_tool_filter_message() == "Invalid tool filter"
    assert invalid_mcp_tool_message().startswith("Invalid tool; expected one of:")
    assert highlight_provider_required_message() == "Highlight provider is required"
    assert invalid_highlight_provider_message() == "Invalid highlight provider"
    assert invalid_model_provider_message() == "model_provider must be 'openai', 'ollama', or 'embedded'."
    assert retrieval_capability_inspection_failed_message("service registry unavailable") == (
        "Retrieval capability inspection failed: service registry unavailable"
    )
    assert snapshot_not_found_message() == "Snapshot not found"
    assert conversation_not_found_message("conv-123") == "Conversation not found: conv-123"
    assert bookmark_not_found_message("conv-123") == "Bookmark for conversation conv-123 not found"
    assert bookmark_removed_message("conv-123") == "Bookmark removed for conversation conv-123"
    assert bookmark_notes_updated_message() == "Notes updated successfully"
    assert saved_query_not_found_message() == "Saved query not found"
    assert saved_queries_file_invalid_message() == "Saved queries file is invalid."
    assert saved_query_missing_created_at_message() == "Saved query is missing created_at."
    assert saved_query_name_required_message() == "Saved query name is required."
    assert saved_query_text_required_message() == "Saved query text is required."
    assert saved_query_filters_required_message() == "Saved query filters must be provided."
    assert saved_query_mode_required_message() == "Saved query mode is required."
    assert saved_query_use_count_invalid_message() == "Saved query use_count is invalid."
    assert dashboards_disabled_message() == "Dashboards are disabled"
    assert dashboard_not_found_message() == "Dashboard not found"
    assert dashboards_file_invalid_message() == "Dashboards file is invalid."
    assert dashboard_missing_created_at_message() == "Dashboard is missing created_at."
    assert dashboard_name_required_message() == "Dashboard name is required."
    assert dashboard_refresh_interval_invalid_message() == "Dashboard refresh_interval must be an integer."
    assert dashboard_layout_required_message() == "Dashboard layout is required."
    assert dashboard_layout_widgets_required_message() == "Dashboard layout widgets are required."
    assert dashboard_widget_object_required_message() == "Dashboard widget must be an object."
    assert dashboard_widget_query_id_required_message() == "Dashboard widget query_id is required."
    assert dashboard_widget_title_invalid_message() == "Dashboard widget title must be a string."
    assert dashboard_widget_limit_invalid_message() == "Dashboard widget limit must be an integer."
    assert dashboard_widget_sort_by_invalid_message() == "Dashboard widget sort_by must be a string."
    assert dashboard_widget_layout_invalid_message() == "Dashboard widget layout must be an object."
    assert dashboard_widget_id_invalid_message() == "Dashboard widget id must be a string."
    assert dashboard_layout_columns_invalid_message() == "Dashboard layout columns must be an integer."
    assert dashboard_queries_invalid_message() == "Dashboard queries must be a list of strings."
    assert dashboard_queries_missing_widget_ids_message() == "Dashboard queries must include all widget query ids."
    assert analytics_active_dataset_only_message() == "Analytics is available only for the active dataset"
    assert internal_server_error_message() == "Internal server error"
    assert backup_operations_disabled_message() == "Backup operations are disabled in snapshot mode"
    assert backup_validation_unavailable_message() == "Backup validation is not available"
    assert backup_chain_resolution_unavailable_message() == "Backup chain resolution is not available"
    assert backup_not_found_message("backup-1") == "Backup not found: backup-1"
    assert backup_summary_unavailable_message() == "Backup summary unavailable"
    assert tech_docs_disabled_message() == "Tech docs generator is disabled"
    assert reindex_blocked_message().startswith("BLOCKED: Reindexing disabled")
    assert indexing_snapshot_disabled_message() == "Indexing is disabled in snapshot mode"
    assert resume_snapshot_disabled_message() == "Resume is disabled in snapshot mode"
    assert conversation_not_found_message_simple() == "Conversation not found"
    assert unknown_conversation_format_message("/tmp/conv.txt") == "Unknown conversation format: /tmp/conv.txt"
    assert conversation_internal_server_error_message("boom") == "Internal server error: boom"
    assert conversation_not_found_in_index_message() == "Conversation not found in index"
    assert conversation_not_found_in_snapshot_message() == "Conversation not found in snapshot"
    assert conversation_file_missing_with_record_message("/tmp/missing.jsonl").endswith(
        "The file may have been moved or deleted: /tmp/missing.jsonl"
    )
    assert conversation_file_missing_message("/tmp/missing.jsonl") == (
        "Conversation file not found. The file may have been moved or deleted: /tmp/missing.jsonl"
    )
    assert conversation_invalid_json_message() == "Failed to parse conversation file (invalid JSON)"
    assert conversation_encoding_error_message() == "Failed to read conversation file (encoding error)"
    assert export_disabled_message("Notebook") == "Notebook export is disabled"
    assert export_disabled_message("PDF") == "PDF export is disabled"
    assert invalid_export_format_message() == "Invalid format. Use: json, markdown, text, ipynb, or pdf"
    assert bulk_export_no_ids_message() == "No conversation IDs provided"
    assert bulk_export_too_many_message() == "Too many conversations (max 100)"
    assert resume_command_not_found_message("claude") == "Failed to execute command. Make sure claude is installed and in PATH."
    assert saved_query_missing_message("q-1") == "Saved query q-1 not found"
    assert saved_query_invalid_message("q-1") == "Saved query q-1 is invalid"
    assert invalid_saved_query_mode_message() == "Invalid search mode in saved query"
    assert invalid_saved_query_tool_filter_message() == "Invalid tool filter in saved query"
    assert no_embeddings_for_conversation_message() == "No embeddings found for this conversation"
    assert no_similar_conversation_found_message() == "No similar conversation found"
    assert target_conversation_not_found_message() == "Target conversation not found"
    assert invalid_target_conversation_id_message() == "Invalid target conversation id"
    assert mcp_search_limit_message() == "limit must be between 1 and 100"
    assert mcp_similarity_limit_message() == "limit must be between 1 and 20"
    assert mcp_offset_message() == "offset must be >= 0"
