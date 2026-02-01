from __future__ import annotations

import asyncio
import inspect
import json
from datetime import datetime
from pathlib import Path
from typing import Any

from searchat.api.duckdb_store import DuckDBStore
from searchat.config import Config, PathResolver
from searchat.core.search_engine import SearchEngine
from searchat.models import SearchFilters, SearchMode


def _require_mcp() -> Any:
    try:
        from mcp.server.fastmcp import FastMCP  # type: ignore[import-not-found]
    except ImportError as exc:
        raise RuntimeError("MCP support is not installed. Install with: pip install 'searchat[mcp]'") from exc
    return FastMCP


FastMCP = _require_mcp()

mcp = FastMCP(name="Searchat")


def _json_default(value: object) -> str:
    if isinstance(value, datetime):
        return value.isoformat()
    raise TypeError(f"Object of type {type(value).__name__} is not JSON serializable")


def _json_dumps(payload: object) -> str:
    return json.dumps(payload, default=_json_default, ensure_ascii=True)


def _resolve_dataset(search_dir: str | None) -> Path:
    config = Config.load()
    base_dir = PathResolver.get_shared_search_dir(config)
    if search_dir is None or not str(search_dir).strip():
        return base_dir
    resolved = Path(str(search_dir)).expanduser()
    if not resolved.exists():
        raise FileNotFoundError(f"Search directory does not exist: {resolved}")
    return resolved


def _build_services(search_dir: Path) -> tuple[Config, SearchEngine, DuckDBStore]:
    config = Config.load()
    engine = SearchEngine(search_dir, config)
    store = DuckDBStore(search_dir, memory_limit_mb=config.performance.memory_limit_mb)
    return config, engine, store


def _parse_mode(mode: str) -> SearchMode:
    value = (mode or "").lower().strip()
    if value == "hybrid":
        return SearchMode.HYBRID
    if value == "semantic":
        return SearchMode.SEMANTIC
    if value == "keyword":
        return SearchMode.KEYWORD
    raise ValueError("Invalid mode; expected: hybrid, semantic, keyword")


def _parse_tool(tool: str | None) -> str | None:
    if tool is None:
        return None
    value = tool.lower().strip()
    if not value:
        return None
    allowed = {"claude", "vibe", "opencode", "codex", "gemini", "cursor", "continue", "aider"}
    if value not in allowed:
        raise ValueError(f"Invalid tool; expected one of: {', '.join(sorted(allowed))}")
    return value


@mcp.tool(name="search_conversations", description="Search conversation history")
def search_conversations(
    query: str,
    mode: str = "hybrid",
    project_id: str | None = None,
    tool: str | None = None,
    limit: int = 10,
    offset: int = 0,
    search_dir: str | None = None,
) -> str:
    """Search indexed conversations.

    Args:
        query: Query string ("*" for browse)
        mode: hybrid | semantic | keyword
        project_id: Optional project_id filter
        tool: Optional tool filter
        limit: Page size (1-100)
        offset: Pagination offset (>=0)
        search_dir: Optional override search directory

    Returns:
        JSON string payload.
    """
    if limit < 1 or limit > 100:
        raise ValueError("limit must be between 1 and 100")
    if offset < 0:
        raise ValueError("offset must be >= 0")

    dataset_dir = _resolve_dataset(search_dir)
    _config, engine, _store = _build_services(dataset_dir)

    filters = SearchFilters()
    if project_id:
        filters.project_ids = [project_id]

    tool_value = _parse_tool(tool)
    if tool_value is not None:
        filters.tool = tool_value

    results = engine.search(query, mode=_parse_mode(mode), filters=filters)

    sliced = results.results[offset:offset + limit]
    payload = {
        "results": [
            {
                "conversation_id": r.conversation_id,
                "project_id": r.project_id,
                "title": r.title,
                "created_at": r.created_at,
                "updated_at": r.updated_at,
                "message_count": r.message_count,
                "file_path": r.file_path,
                "snippet": r.snippet,
                "score": r.score,
                "message_start_index": r.message_start_index,
                "message_end_index": r.message_end_index,
            }
            for r in sliced
        ],
        "total": len(results.results),
        "limit": limit,
        "offset": offset,
        "mode_used": results.mode_used,
        "search_time_ms": results.search_time_ms,
    }
    return _json_dumps(payload)


@mcp.tool(name="get_conversation", description="Fetch a conversation by id")
def get_conversation(conversation_id: str, search_dir: str | None = None) -> str:
    dataset_dir = _resolve_dataset(search_dir)
    _config, _engine, store = _build_services(dataset_dir)

    record = store.get_conversation_record(conversation_id)
    if record is None:
        raise ValueError(f"Conversation not found: {conversation_id}")

    return _json_dumps(record)


@mcp.tool(name="list_projects", description="List all project ids")
def list_projects(search_dir: str | None = None) -> str:
    dataset_dir = _resolve_dataset(search_dir)
    _config, _engine, store = _build_services(dataset_dir)
    return _json_dumps({"projects": store.list_projects()})


@mcp.tool(name="get_statistics", description="Get index statistics")
def get_statistics(search_dir: str | None = None) -> str:
    dataset_dir = _resolve_dataset(search_dir)
    _config, _engine, store = _build_services(dataset_dir)
    stats = store.get_statistics()
    return _json_dumps({
        "total_conversations": stats.total_conversations,
        "total_messages": stats.total_messages,
        "avg_messages": stats.avg_messages,
        "total_projects": stats.total_projects,
        "earliest_date": stats.earliest_date,
        "latest_date": stats.latest_date,
    })


def run() -> None:
    """Run the MCP server over stdio."""
    result = mcp.run()
    if inspect.isawaitable(result):
        async def _main() -> None:
            await result

        asyncio.run(_main())
