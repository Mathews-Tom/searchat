"""Data models and schemas for searchat."""
from searchat.models.enums import AlgorithmType, SearchMode
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
    FILE_STATE_SCHEMA,
    CODE_BLOCK_SCHEMA,
)

__all__ = [
    # Enums
    "AlgorithmType",
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
    "FILE_STATE_SCHEMA",
    "CODE_BLOCK_SCHEMA",
]
