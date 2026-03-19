"""Shared utility functions for API endpoints."""
from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path

from fastapi import HTTPException
from fastapi.responses import JSONResponse

from searchat.config.constants import VALID_TOOL_NAMES
from searchat.contracts.errors import (
    invalid_model_provider_message,
    invalid_tool_filter_message,
    retrieval_capability_inspection_failed_message,
    snapshot_not_found_message,
)
from searchat.models import SearchResult

VALID_PROVIDERS: frozenset[str] = frozenset({"openai", "ollama", "embedded"})


class RetrievalCapabilitiesUnavailable(RuntimeError):
    """Raised when retrieval capabilities cannot be inspected for a semantic-gated request."""


def detect_tool_from_path(file_path: str) -> str:
    """
    Detect tool type from a conversation file path.

    Args:
        file_path: Path to conversation file

    Returns:
        Tool name: 'claude', 'vibe', 'opencode', 'codex', 'gemini', 'continue', 'cursor', or 'aider'
    """
    normalized = file_path.lower().replace("\\", "/")

    if "/.local/share/opencode/" in normalized:
        return "opencode"

    if "/.codex/" in normalized:
        return "codex"

    if "/.continue/sessions/" in normalized and normalized.endswith(".json"):
        return "continue"

    if ".vscdb.cursor/" in normalized and normalized.endswith(".json"):
        return "cursor"

    if "/.gemini/tmp/" in normalized and "/chats/" in normalized and normalized.endswith(".json"):
        return "gemini"

    if normalized.endswith("/.aider.chat.history.md") or normalized.endswith(".aider.chat.history.md"):
        return "aider"

    if "/.claude/" in normalized and normalized.endswith(".jsonl"):
        return "claude"

    if "/.vibe/" in normalized and normalized.endswith(".json"):
        return "vibe"

    if normalized.endswith(".jsonl"):
        return "claude"

    return "vibe"


def detect_source_from_path(file_path: str) -> str:
    """
    Detect source environment (WIN or WSL) from file path.

    Args:
        file_path: Path to conversation file

    Returns:
        Source: 'WSL' or 'WIN'
    """
    file_path_lower = file_path.lower()
    if "/home/" in file_path_lower or "wsl" in file_path_lower:
        return "WSL"
    return "WIN"


def parse_date_filter(
    date_preset: str | None,
    date_from: str | None,
    date_to: str | None
) -> tuple[datetime | None, datetime | None]:
    """
    Parse date filter parameters into datetime objects.

    Args:
        date_preset: Preset filter ('today', 'week', 'month', 'custom')
        date_from: Custom date from (YYYY-MM-DD)
        date_to: Custom date to (YYYY-MM-DD)

    Returns:
        Tuple of (date_from, date_to) as datetime objects or None
    """
    result_from: datetime | None = None
    result_to: datetime | None = None

    if date_preset == "custom" and (date_from or date_to):
        if date_from:
            result_from = datetime.fromisoformat(date_from)
        if date_to:
            # Add 1 day to include the entire end date
            result_to = datetime.fromisoformat(date_to) + timedelta(days=1)
    elif date_preset:
        now = datetime.now()
        if date_preset == "today":
            result_from = now.replace(hour=0, minute=0, second=0, microsecond=0)
            result_to = now
        elif date_preset == "week":
            result_from = now - timedelta(days=7)
            result_to = now
        elif date_preset == "month":
            result_from = now - timedelta(days=30)
            result_to = now

    return result_from, result_to


def resolve_dataset(snapshot: str | None) -> tuple[Path, str | None]:
    """Resolve snapshot parameter into a search directory and snapshot name.

    Raises HTTPException with 404/400 for invalid snapshots.
    """
    import searchat.api.dependencies as deps

    try:
        return deps.resolve_dataset_search_dir(snapshot)
    except ValueError as exc:
        msg = str(exc)
        if msg == snapshot_not_found_message():
            raise HTTPException(status_code=404, detail=snapshot_not_found_message()) from exc
        raise HTTPException(status_code=400, detail=msg) from exc


def validate_tool(tool: str) -> str:
    """Validate and normalize a tool filter value. Returns lowered value."""
    tool_value = tool.lower()
    if tool_value not in VALID_TOOL_NAMES:
        raise HTTPException(status_code=400, detail=invalid_tool_filter_message())
    return tool_value


def validate_provider(provider: str) -> str:
    """Validate and normalize an LLM provider value. Returns lowered value."""
    value = provider.lower()
    if value not in VALID_PROVIDERS:
        raise HTTPException(
            status_code=400,
            detail=invalid_model_provider_message(),
        )
    return value


def check_semantic_readiness(
    extra_components: list[str] | None = None,
    retrieval_service=None,
) -> JSONResponse | None:
    """Check if semantic search components are ready.

    Returns None if ready, or an error/warming JSONResponse otherwise.
    Also triggers warmup if components are not yet ready.
    """
    from searchat.api import readiness as _readiness_mod
    from searchat.api import warmup as _warmup

    readiness = _readiness_mod.get_readiness().snapshot()
    required = ["metadata", "faiss", "embedder"]
    if extra_components:
        required.extend(extra_components)

    for key in required:
        if readiness.components.get(key) == "error":
            return JSONResponse(status_code=500, content=_readiness_mod.error_payload())

    if any(readiness.components.get(key) != "ready" for key in required):
        _warmup.trigger_search_engine_warmup()
        return JSONResponse(status_code=503, content=_readiness_mod.warming_payload())

    try:
        capabilities = _get_retrieval_capabilities(retrieval_service, fail_closed=True)
    except RetrievalCapabilitiesUnavailable as exc:
        payload = _readiness_mod.error_payload()
        errors = dict(payload["errors"])
        errors["semantic"] = str(exc)
        payload["errors"] = errors
        return JSONResponse(status_code=500, content=payload)

    if capabilities is not None and not capabilities.semantic_available:
        payload = _readiness_mod.error_payload()
        errors = dict(payload["errors"])
        if capabilities.semantic_reason:
            errors["semantic"] = capabilities.semantic_reason
        payload["errors"] = errors
        payload["capabilities"] = {
            "semantic_available": capabilities.semantic_available,
            "reranking_available": capabilities.reranking_available,
            "semantic_reason": capabilities.semantic_reason,
            "reranking_reason": capabilities.reranking_reason,
        }
        return JSONResponse(status_code=500, content=payload)

    return None


def get_retrieval_capabilities_snapshot() -> dict[str, object] | None:
    """Best-effort retrieval capability snapshot for status endpoints."""
    try:
        capabilities = _get_retrieval_capabilities()
    except RetrievalCapabilitiesUnavailable:
        return None
    if capabilities is None:
        return None
    return {
        "semantic_available": capabilities.semantic_available,
        "reranking_available": capabilities.reranking_available,
        "semantic_reason": capabilities.semantic_reason,
        "reranking_reason": capabilities.reranking_reason,
    }


def _get_retrieval_capabilities(retrieval_service=None, *, fail_closed: bool = False):
    """Return retrieval capabilities when a semantic retrieval service is available."""
    service = retrieval_service
    if service is None:
        import searchat.api.dependencies as deps

        service = getattr(deps, "_search_engine", None)
        if service is None:
            return None
    elif callable(service):
        try:
            service = service()
        except Exception as exc:
            if fail_closed:
                raise RetrievalCapabilitiesUnavailable(
                    retrieval_capability_inspection_failed_message(str(exc))
                ) from exc
            return None

    describe = getattr(service, "describe_capabilities", None)
    if not callable(describe):
        return None

    try:
        return describe()
    except Exception as exc:
        if fail_closed:
            raise RetrievalCapabilitiesUnavailable(
                retrieval_capability_inspection_failed_message(str(exc))
            ) from exc
        return None


def sort_results(results: list[SearchResult], sort_by: str) -> list[SearchResult]:
    """Sort search results by the given sort_by parameter."""
    sorted_results = results.copy()
    if sort_by == "date_newest":
        sorted_results.sort(key=lambda r: r.updated_at, reverse=True)
    elif sort_by == "date_oldest":
        sorted_results.sort(key=lambda r: r.updated_at, reverse=False)
    elif sort_by == "messages":
        sorted_results.sort(key=lambda r: r.message_count, reverse=True)
    return sorted_results


def search_result_to_response(r: SearchResult) -> object:
    """Convert a SearchResult domain object to a SearchResultResponse dict."""
    from searchat.api.contracts import serialize_search_result

    return serialize_search_result(r)


def ensure_code_index_has_symbol_columns(conn, parquet_glob: str) -> None:
    """Fail fast if the code index doesn't include symbol metadata columns."""
    try:
        cursor = conn.execute("SELECT * FROM parquet_scan(?) LIMIT 0", [parquet_glob])
    except Exception as exc:
        raise HTTPException(
            status_code=503,
            detail=f"Failed to read code index schema: {exc}",
        ) from exc

    columns: set[str] = set()
    for desc in getattr(cursor, "description", []) or []:
        if desc and isinstance(desc[0], str):
            columns.add(desc[0])

    required = {"functions", "classes", "imports"}
    if not required.issubset(columns):
        raise HTTPException(
            status_code=503,
            detail="Code index does not include symbol metadata. "
            "Rebuild the index to enable symbol filters.",
        )


def rows_to_code_results(rows: list) -> tuple[int, list]:
    """Convert DuckDB code search rows to (total, list[CodeSearchResultResponse]).

    Expects rows from a SELECT with count(*) OVER() as last column.
    """
    from searchat.api.models import CodeSearchResultResponse

    total = int(rows[0][-1]) if rows else 0
    results = []
    for (
        conversation_id,
        project_id,
        title,
        file_path,
        connector,
        message_index,
        block_index,
        role,
        language_value,
        language_source,
        fence_language,
        lines,
        code,
        code_hash,
        conversation_updated_at,
        _total_count,
    ) in rows:
        code_text = code or ""
        max_chars = 4000
        if len(code_text) > max_chars:
            code_text = code_text[:max_chars]

        updated_at_str = (
            conversation_updated_at
            if isinstance(conversation_updated_at, str)
            else conversation_updated_at.isoformat()
        )
        results.append(
            CodeSearchResultResponse(
                conversation_id=conversation_id,
                project_id=project_id,
                title=title,
                file_path=file_path,
                tool=connector,
                message_index=int(message_index),
                block_index=int(block_index),
                role=role,
                language=language_value,
                language_source=language_source,
                fence_language=fence_language,
                lines=int(lines),
                code=code_text,
                code_hash=code_hash,
                conversation_updated_at=updated_at_str,
            )
        )
    return total, results
