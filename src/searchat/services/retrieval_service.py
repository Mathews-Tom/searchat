"""Retrieval-facing service contract used by non-API application services."""
from __future__ import annotations

from typing import Protocol

from searchat.models import SearchFilters, SearchMode, SearchResults


class RetrievalService(Protocol):
    """Minimal retrieval contract for archive-backed search workflows."""

    def search(self, query: str, mode: SearchMode, filters: SearchFilters) -> SearchResults:
        """Execute a search against the conversation archive."""

