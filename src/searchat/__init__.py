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
from searchat.core import ConversationIndexer

__all__ = [
    "ConversationRecord",
    "MessageRecord",
    "SearchResult",
    "SearchResults",
    "SearchMode",
    "SearchFilters",
    "ConversationIndexer",
]
