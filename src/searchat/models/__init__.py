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
    FileTouched,
    DistilledObject,
    Room,
    RoomObject,
    DistillationStats,
    PalaceSearchResult,
)
try:
    from searchat.models.schemas import (
        CONVERSATION_SCHEMA,
        METADATA_SCHEMA,
        FILE_STATE_SCHEMA,
        CODE_BLOCK_SCHEMA,
    )
except ImportError:
    # pyarrow is an optional [legacy] dependency — schemas unavailable without it
    pass

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
    # Palace / Distillation
    "FileTouched",
    "DistilledObject",
    "Room",
    "RoomObject",
    "DistillationStats",
    "PalaceSearchResult",
    # Schemas
    "CONVERSATION_SCHEMA",
    "METADATA_SCHEMA",
    "FILE_STATE_SCHEMA",
    "CODE_BLOCK_SCHEMA",
]
