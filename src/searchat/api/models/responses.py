"""Pydantic response models for API endpoints."""
from __future__ import annotations

from pydantic import BaseModel


class SearchResultResponse(BaseModel):
    """Single search result in API response."""
    conversation_id: str
    project_id: str
    title: str
    created_at: str
    updated_at: str
    message_count: int
    file_path: str
    snippet: str
    score: float
    message_start_index: int | None = None
    message_end_index: int | None = None
    source: str  # WIN or WSL
    tool: str


class ConversationMessage(BaseModel):
    """Message in conversation response."""
    role: str
    content: str
    timestamp: str


class ConversationResponse(BaseModel):
    """Full conversation details."""
    conversation_id: str
    title: str
    project_id: str
    project_path: str | None = None
    file_path: str
    message_count: int
    tool: str
    messages: list[ConversationMessage]


class BackupMetadataResponse(BaseModel):
    """Backup metadata."""
    backup_path: str
    backup_name: str
    created_at: str
    file_count: int
    total_size_bytes: int


class BackupCreateResponse(BaseModel):
    """Backup creation result."""
    message: str
    backup_name: str
    backup_path: str
    file_count: int
    total_size_mb: float


class BackupListResponse(BaseModel):
    """List of available backups."""
    backups: list[BackupMetadataResponse]


class BackupRestoreResponse(BaseModel):
    """Backup restore result."""
    message: str
    backup_name: str
    restored_files: int


class ConversationSource(BaseModel):
    """Source metadata for a RAG answer."""

    conversation_id: str
    project_id: str
    title: str
    file_path: str
    updated_at: str
    score: float
    snippet: str
    message_start_index: int | None = None
    message_end_index: int | None = None
    source: str
    tool: str


class RAGResponse(BaseModel):
    """Non-streaming chat response with sources."""

    answer: str
    sources: list[ConversationSource]
    context_used: int


class CodeSearchResultResponse(BaseModel):
    conversation_id: str
    project_id: str
    title: str
    file_path: str
    tool: str
    message_index: int
    block_index: int
    role: str
    language: str
    language_source: str
    fence_language: str | None = None
    lines: int
    code: str
    code_hash: str
    conversation_updated_at: str


class CodeSearchResponse(BaseModel):
    results: list[CodeSearchResultResponse]
    total: int
    limit: int
    offset: int
    has_more: bool
