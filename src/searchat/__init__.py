__version__ = "0.2.0"
__author__ = "Searchat Contributors"

from searchat.models import (
    ConversationRecord,
    MessageRecord,
    SearchResult,
    SearchResults,
    SearchMode,
    SearchFilters,
)
from searchat.core import (
    SearchEngine,
    ConversationIndexer,
)

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