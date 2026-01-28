"""Shared utility functions for API endpoints."""
from __future__ import annotations

from datetime import datetime, timedelta


def detect_tool_from_path(file_path: str) -> str:
    """
    Detect tool type (claude, vibe, opencode) from file path.

    Args:
        file_path: Path to conversation file

    Returns:
        Tool name: 'claude', 'vibe', or 'opencode'
    """
    file_path_lower = file_path.lower()
    if file_path.endswith('.jsonl'):
        return "claude"
    if "/.local/share/opencode/" in file_path_lower:
        return "opencode"
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
