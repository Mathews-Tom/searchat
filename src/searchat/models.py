from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import List, Optional
import pyarrow as pa


class SearchMode(Enum):
    KEYWORD = "keyword"
    SEMANTIC = "semantic"
    HYBRID = "hybrid"


@dataclass
class MessageRecord:
    sequence: int
    role: str
    content: str
    timestamp: datetime
    has_code: bool
    code_blocks: List[str] = field(default_factory=list)


@dataclass
class ConversationRecord:
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
    project_ids: Optional[List[str]] = None
    date_from: Optional[datetime] = None
    date_to: Optional[datetime] = None
    min_messages: int = 0
    has_code: Optional[bool] = None
    tool: str | None = None


@dataclass
class SearchResult:
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
    results: List[SearchResult]
    total_count: int
    search_time_ms: float
    mode_used: str
    error: Optional[str] = None


@dataclass
class IndexStats:
    total_conversations: int
    total_messages: int
    index_time_seconds: float
    parquet_size_mb: float
    faiss_size_mb: float


@dataclass
class UpdateStats:
    new_conversations: int
    updated_conversations: int
    skipped_conversations: int
    update_time_seconds: float


@dataclass
class DateFilter:
    from_date: Optional[datetime]
    to_date: Optional[datetime]


@dataclass
class ParsedQuery:
    original: str
    must_include: List[str] = field(default_factory=list)
    should_include: List[str] = field(default_factory=list)
    must_exclude: List[str] = field(default_factory=list)
    exact_phrases: List[str] = field(default_factory=list)
    date_filter: Optional[DateFilter] = None


CONVERSATION_SCHEMA = pa.schema([
    ('conversation_id', pa.string()),
    ('project_id', pa.string()),
    ('file_path', pa.string()),
    ('title', pa.string()),
    ('created_at', pa.timestamp('us')),
    ('updated_at', pa.timestamp('us')),
    ('message_count', pa.int32()),
    ('messages', pa.list_(
        pa.struct([
            ('sequence', pa.int32()),
            ('role', pa.string()),
            ('content', pa.string()),
            ('timestamp', pa.timestamp('us')),
            ('has_code', pa.bool_()),
            ('code_blocks', pa.list_(pa.string()))
        ])
    )),
    ('full_text', pa.string()),
    ('embedding_id', pa.int64()),
    ('file_hash', pa.string()),
    ('indexed_at', pa.timestamp('us'))
])

METADATA_SCHEMA = pa.schema([
    ('vector_id', pa.int64()),
    ('conversation_id', pa.string()),
    ('project_id', pa.string()),
    ('chunk_index', pa.int32()),
    ('chunk_text', pa.string()),
    ('message_start_index', pa.int32()),
    ('message_end_index', pa.int32()),
    ('created_at', pa.timestamp('us'))
])
