"""Shared SQL filter generation for tool-based queries.

Centralizes the tool → SQL WHERE condition mapping used by
SearchEngine, DuckDBStore, and API routers.
"""
from __future__ import annotations

from searchat.config.constants import VALID_TOOL_NAMES

# Per-tool SQL inclusion conditions.
# Each maps a tool name to a list of SQL conditions (joined with OR internally).
_TOOL_INCLUDE: dict[str, list[str]] = {
    "opencode":  ["project_id LIKE 'opencode-%'"],
    "vibe":      ["project_id LIKE 'vibe-%'"],
    "codex":     ["project_id = 'codex'", "file_path ILIKE '%/.codex/%'"],
    "gemini":    [
        "project_id = 'gemini'",
        "project_id LIKE 'gemini-%'",
        "file_path ILIKE '%/.gemini/tmp/%/chats/%'",
    ],
    "continue":  ["project_id LIKE 'continue-%'", "file_path ILIKE '%/.continue/sessions/%'"],
    "cursor":    ["project_id LIKE 'cursor-%'", "file_path ILIKE '%.vscdb.cursor/%'"],
    "aider":     ["project_id LIKE 'aider-%'", "file_path ILIKE '%/.aider.chat.history.md'"],
}

# Tools whose project_id patterns must be excluded when filtering for "claude".
_NON_CLAUDE_LIKE_PATTERNS: list[str] = [
    "project_id NOT LIKE 'opencode-%'",
    "project_id NOT LIKE 'vibe-%'",
    "project_id NOT LIKE 'gemini-%'",
    "project_id NOT LIKE 'continue-%'",
    "project_id NOT LIKE 'cursor-%'",
    "project_id NOT LIKE 'aider-%'",
    "project_id != 'gemini'",
    "project_id != 'codex'",
]


def tool_sql_conditions(tool: str, *, prefix: str = "") -> list[str]:
    """Return SQL WHERE conditions for filtering conversations by tool.

    Args:
        tool: Validated tool name (one of VALID_TOOL_NAMES).
        prefix: Optional table alias prefix (e.g. ``"c"`` produces ``c.project_id``).

    Returns:
        List of SQL condition strings to AND into a WHERE clause.

    Raises:
        ValueError: If *tool* is not a recognized tool name.
    """
    if tool not in VALID_TOOL_NAMES:
        raise ValueError(f"Unknown tool: {tool!r}")

    pfx = f"{prefix}." if prefix else ""

    if tool == "claude":
        return [f"{pfx}{cond}" for cond in _NON_CLAUDE_LIKE_PATTERNS]

    include = _TOOL_INCLUDE[tool]
    if len(include) == 1:
        return [f"{pfx}{include[0]}"]
    return [f"({' OR '.join(f'{pfx}{c}' for c in include)})"]
