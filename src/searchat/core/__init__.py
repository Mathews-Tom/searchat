"""Core business logic - indexing and search."""
from __future__ import annotations

from searchat.core.query_parser import QueryParser
from searchat.core.watcher import ConversationWatcher

__all__ = [
    "ConversationIndexer",
    "QueryParser",
    "ConversationWatcher",
]


def __getattr__(name: str):
    if name == "ConversationIndexer":
        from searchat.core.indexer import ConversationIndexer
        return ConversationIndexer
    raise AttributeError(f"module 'searchat.core' has no attribute {name!r}")
