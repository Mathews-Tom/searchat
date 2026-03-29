"""Conversation filter — excludes automated/noise conversations from results.

Filters out conversations that are likely automated (CI bots, system-generated)
or too short to contain meaningful content, improving search result quality.
"""
from __future__ import annotations

import re

from searchat.models.domain import SearchResult

# Title patterns indicating automated conversations
_AUTOMATED_PATTERNS: list[re.Pattern[str]] = [
    re.compile(r"^(auto|system|bot|ci|cd|cron|scheduled)\b", re.IGNORECASE),
    re.compile(r"\b(automated|auto-generated|system-generated)\b", re.IGNORECASE),
    re.compile(r"^test\s*run\s*#?\d+", re.IGNORECASE),
]


class ConversationFilter:
    """Filters search results to exclude noise conversations."""

    def __init__(
        self,
        *,
        min_message_count: int = 2,
        exclude_automated: bool = True,
    ) -> None:
        self._min_messages = min_message_count
        self._exclude_automated = exclude_automated

    def filter(self, results: list[SearchResult]) -> list[SearchResult]:
        """Apply all filters to a result list, preserving order."""
        return [r for r in results if self._keep(r)]

    def _keep(self, result: SearchResult) -> bool:
        if result.message_count < self._min_messages:
            return False

        if self._exclude_automated and self._is_automated(result.title):
            return False

        return True

    @staticmethod
    def _is_automated(title: str) -> bool:
        if not title:
            return False
        return any(p.search(title) for p in _AUTOMATED_PATTERNS)
