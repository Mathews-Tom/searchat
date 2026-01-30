"""Core business logic - indexing and search."""
from __future__ import annotations

from searchat.core.indexer import ConversationIndexer
from searchat.core.query_parser import QueryParser
from searchat.core.watcher import ConversationWatcher

__all__ = [
    "ConversationIndexer",
    "SearchEngine",
    "QueryParser",
    "ConversationWatcher",
]


def __getattr__(name: str):
    if name == "SearchEngine":
        from searchat.core.search_engine import SearchEngine

        return SearchEngine
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
