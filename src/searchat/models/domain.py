"""Domain models for searchat - business logic data structures."""
from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Optional


@dataclass
class MessageRecord:
    """Record representing a single message in a conversation."""
    sequence: int
    role: str
    content: str
    timestamp: datetime
    has_code: bool
    code_blocks: List[str] = field(default_factory=list)


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
    messages: List[MessageRecord]
    full_text: str
    embedding_id: int
    file_hash: str
    indexed_at: datetime


@dataclass
class SearchFilters:
    """Filters for search queries."""
    project_ids: Optional[List[str]] = None
    date_from: Optional[datetime] = None
    date_to: Optional[datetime] = None
    min_messages: int = 0
    has_code: Optional[bool] = None


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
    message_start_index: Optional[int] = None
    message_end_index: Optional[int] = None


@dataclass
class SearchResults:
    """Collection of search results with metadata."""
    results: List[SearchResult]
    total_count: int
    search_time_ms: float
    mode_used: str
    error: Optional[str] = None


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


@dataclass
class DateFilter:
    """Date range filter for search queries."""
    from_date: Optional[datetime]
    to_date: Optional[datetime]


@dataclass
class ParsedQuery:
    """Parsed search query with extracted components."""
    original: str
    must_include: List[str] = field(default_factory=list)
    should_include: List[str] = field(default_factory=list)
    must_exclude: List[str] = field(default_factory=list)
    exact_phrases: List[str] = field(default_factory=list)
    date_filter: Optional[DateFilter] = None
