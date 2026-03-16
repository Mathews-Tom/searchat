from __future__ import annotations

from searchat.config.constants import VALID_TOOL_NAMES


def invalid_search_mode_message() -> str:
    return "Invalid search mode"


def invalid_mcp_mode_message() -> str:
    return "Invalid mode; expected: hybrid, semantic, keyword"


def invalid_tool_filter_message() -> str:
    return "Invalid tool filter"


def invalid_mcp_tool_message() -> str:
    return f"Invalid tool; expected one of: {', '.join(sorted(VALID_TOOL_NAMES))}"


def highlight_provider_required_message() -> str:
    return "Highlight provider is required"


def invalid_highlight_provider_message() -> str:
    return "Invalid highlight provider"


def snapshot_not_found_message() -> str:
    return "Snapshot not found"


def conversation_not_found_message(conversation_id: str) -> str:
    return f"Conversation not found: {conversation_id}"


def bookmark_not_found_message(conversation_id: str) -> str:
    return f"Bookmark for conversation {conversation_id} not found"


def saved_query_not_found_message() -> str:
    return "Saved query not found"


def dashboards_disabled_message() -> str:
    return "Dashboards are disabled"


def dashboard_not_found_message() -> str:
    return "Dashboard not found"


def saved_query_missing_message(query_id: object) -> str:
    return f"Saved query {query_id} not found"


def saved_query_invalid_message(query_id: object) -> str:
    return f"Saved query {query_id} is invalid"


def invalid_saved_query_mode_message() -> str:
    return "Invalid search mode in saved query"


def invalid_saved_query_tool_filter_message() -> str:
    return "Invalid tool filter in saved query"


def analytics_active_dataset_only_message() -> str:
    return "Analytics is available only for the active dataset"


def internal_server_error_message() -> str:
    return "Internal server error"


def backup_operations_disabled_message() -> str:
    return "Backup operations are disabled in snapshot mode"


def backup_validation_unavailable_message() -> str:
    return "Backup validation is not available"


def backup_chain_resolution_unavailable_message() -> str:
    return "Backup chain resolution is not available"


def backup_not_found_message(backup_name: str) -> str:
    return f"Backup not found: {backup_name}"


def backup_summary_unavailable_message() -> str:
    return "Backup summary unavailable"


def tech_docs_disabled_message() -> str:
    return "Tech docs generator is disabled"


def reindex_blocked_message() -> str:
    return (
        "BLOCKED: Reindexing disabled to protect irreplaceable conversation data. "
        "Source JSONLs are missing - rebuilding would cause data loss."
    )


def indexing_snapshot_disabled_message() -> str:
    return "Indexing is disabled in snapshot mode"


def resume_snapshot_disabled_message() -> str:
    return "Resume is disabled in snapshot mode"


def conversation_not_found_message_simple() -> str:
    return "Conversation not found"


def conversation_not_found_in_index_message() -> str:
    return "Conversation not found in index"


def conversation_not_found_in_snapshot_message() -> str:
    return "Conversation not found in snapshot"


def conversation_file_missing_with_record_message(file_path: str) -> str:
    return (
        "Conversation file not found and no indexed record is available. "
        f"The file may have been moved or deleted: {file_path}"
    )


def conversation_file_missing_message(file_path: str) -> str:
    return f"Conversation file not found. The file may have been moved or deleted: {file_path}"


def conversation_invalid_json_message() -> str:
    return "Failed to parse conversation file (invalid JSON)"


def conversation_encoding_error_message() -> str:
    return "Failed to read conversation file (encoding error)"


def export_disabled_message(format_name: str) -> str:
    return f"{format_name} export is disabled"


def invalid_export_format_message() -> str:
    return "Invalid format. Use: json, markdown, text, ipynb, or pdf"


def bulk_export_no_ids_message() -> str:
    return "No conversation IDs provided"


def bulk_export_too_many_message() -> str:
    return "Too many conversations (max 100)"


def resume_command_not_found_message(tool_name: str) -> str:
    return f"Failed to execute command. Make sure {tool_name} is installed and in PATH."


def no_embeddings_for_conversation_message() -> str:
    return "No embeddings found for this conversation"


def no_similar_conversation_found_message() -> str:
    return "No similar conversation found"


def target_conversation_not_found_message() -> str:
    return "Target conversation not found"


def invalid_target_conversation_id_message() -> str:
    return "Invalid target conversation id"


def mcp_search_limit_message() -> str:
    return "limit must be between 1 and 100"


def mcp_similarity_limit_message() -> str:
    return "limit must be between 1 and 20"


def mcp_offset_message() -> str:
    return "offset must be >= 0"
