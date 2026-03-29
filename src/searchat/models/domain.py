"""Domain models for searchat - business logic data structures."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class MessageRecord:
    """Record representing a single message in a conversation."""
    sequence: int
    role: str
    content: str
    timestamp: datetime
    has_code: bool
    code_blocks: list[str] = field(default_factory=list)


@dataclass
class ConversationRecord:
    """Record representing a full conversation with metadata."""
    conversation_id: str
    project_id: str
    file_path: str
    title: str
    created_at: datetime
    updated_at: datetime
    message_count: int
    messages: list[MessageRecord]
    full_text: str
    embedding_id: int
    file_hash: str
    indexed_at: datetime
    files_mentioned: list[str] | None = None
    git_branch: str | None = None


@dataclass
class SearchFilters:
    """Filters for search queries."""
    project_ids: list[str] | None = None
    date_from: datetime | None = None
    date_to: datetime | None = None
    min_messages: int = 0
    has_code: bool | None = None
    tool: str | None = None


@dataclass
class SearchResult:
    """Single search result with metadata and score."""
    conversation_id: str
    project_id: str
    title: str
    created_at: datetime
    updated_at: datetime
    message_count: int
    file_path: str
    score: float
    snippet: str
    message_start_index: int | None = None
    message_end_index: int | None = None
    # V2 fields — optional for backward compatibility
    exchange_id: str | None = None
    exchange_text: str | None = None
    bm25_score: float | None = None
    semantic_score: float | None = None


@dataclass
class SearchResults:
    """Collection of search results with metadata."""
    results: list[SearchResult]
    total_count: int
    search_time_ms: float
    mode_used: str
    error: str | None = None


@dataclass
class IndexStats:
    """Statistics about the search index."""
    total_conversations: int
    total_messages: int
    index_time_seconds: float
    parquet_size_mb: float
    faiss_size_mb: float


@dataclass
class UpdateStats:
    """Statistics about an incremental index update."""
    new_conversations: int
    updated_conversations: int
    skipped_conversations: int
    update_time_seconds: float
    empty_conversations: int = 0


@dataclass
class DateFilter:
    """Date range filter for search queries."""
    from_date: datetime | None
    to_date: datetime | None


@dataclass
class ParsedQuery:
    """Parsed search query with extracted components."""
    original: str
    must_include: list[str] = field(default_factory=list)
    should_include: list[str] = field(default_factory=list)
    must_exclude: list[str] = field(default_factory=list)
    exact_phrases: list[str] = field(default_factory=list)
    date_filter: DateFilter | None = None


# ============================================================================
# Palace / Distillation Models
# ============================================================================


@dataclass
class FileTouched:
    """A file referenced in a distilled exchange."""
    path: str
    action: str  # read | modified | created | deleted | discussed | referenced


@dataclass
class DistilledObject:
    """A distilled representation of a conversation exchange."""
    object_id: str
    project_id: str
    conversation_id: str
    ply_start: int
    ply_end: int
    files_touched: list[FileTouched]
    exchange_core: str
    specific_context: str
    created_at: datetime
    exchange_at: datetime
    embedding_id: int
    distilled_text: str
    conv_title: str | None = None


@dataclass
class Room:
    """A thematic room in the memory palace."""
    room_id: str
    room_type: str  # file | module | concept | tool | workflow
    room_key: str
    room_label: str
    project_id: str | None
    created_at: datetime
    updated_at: datetime
    object_count: int


@dataclass
class RoomObject:
    """Junction record linking a room to a distilled object."""
    room_id: str
    object_id: str
    relevance: float
    placed_at: datetime


@dataclass
class DistillationStats:
    """Statistics from a distillation run."""
    conversations_processed: int
    objects_created: int
    rooms_created: int
    rooms_updated: int
    distillation_time_seconds: float


@dataclass
class PalaceSearchResult:
    """Search result from palace layer with full metadata."""
    object_id: str
    conversation_id: str
    project_id: str
    ply_start: int
    ply_end: int
    exchange_core: str
    specific_context: str
    files_touched: list[FileTouched]
    rooms: list[Room]
    score: float
    keyword_score: float = 0.0
    semantic_score: float = 0.0
