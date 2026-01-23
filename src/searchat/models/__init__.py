"""Data models and schemas for searchat."""
from searchat.models.enums import SearchMode
from searchat.models.domain import (
    MessageRecord,
    ConversationRecord,
    SearchFilters,
    SearchResult,
    SearchResults,
    IndexStats,
    UpdateStats,
    DateFilter,
    ParsedQuery,
)
from searchat.models.schemas import (
    CONVERSATION_SCHEMA,
    METADATA_SCHEMA,
)

__all__ = [
    # Enums
    "SearchMode",
    # Domain models
    "MessageRecord",
    "ConversationRecord",
    "SearchFilters",
    "SearchResult",
    "SearchResults",
    "IndexStats",
    "UpdateStats",
    "DateFilter",
    "ParsedQuery",
    # Schemas
    "CONVERSATION_SCHEMA",
    "METADATA_SCHEMA",
]
