from __future__ import annotations

__version__ = "0.7.0"
__author__ = "Searchat Contributors"

from searchat.models import (
    ConversationRecord,
    MessageRecord,
    SearchResult,
    SearchResults,
    SearchMode,
    SearchFilters,
)

__all__ = [
    "ConversationRecord",
    "MessageRecord",
    "SearchResult",
    "SearchResults",
    "SearchMode",
    "SearchFilters",
    "ConversationIndexer",
]


def __getattr__(name: str):
    if name == "ConversationIndexer":
        from searchat.core.indexer import ConversationIndexer
        return ConversationIndexer
    raise AttributeError(f"module 'searchat' has no attribute {name!r}")
