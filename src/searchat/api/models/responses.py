"""Pydantic response models for API endpoints."""
from typing import List, Optional
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
    message_start_index: Optional[int] = None
    message_end_index: Optional[int] = None
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
    project_path: Optional[str] = None
    file_path: str
    message_count: int
    tool: str
    messages: List[ConversationMessage]


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
    backups: List[BackupMetadataResponse]


class BackupRestoreResponse(BaseModel):
    """Backup restore result."""
    message: str
    backup_name: str
    restored_files: int
