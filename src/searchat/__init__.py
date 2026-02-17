from __future__ import annotations

__version__ = "0.6.1"
__author__ = "Searchat Contributors"

from searchat.models import (
    ConversationRecord,
    MessageRecord,
    SearchResult,
    SearchResults,
    SearchMode,
    SearchFilters,
)
from searchat.core import ConversationIndexer

__all__ = [
    "ConversationRecord",
    "MessageRecord",
    "SearchResult",
    "SearchResults",
    "SearchMode",
    "SearchFilters",
    "SearchEngine",
    "ConversationIndexer",
]


def __getattr__(name: str):
    if name == "SearchEngine":
        from searchat.core.search_engine import SearchEngine

        return SearchEngine
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
