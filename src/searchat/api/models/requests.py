"""Pydantic request models for API endpoints."""
from typing import Optional
from pydantic import BaseModel


class SearchRequest(BaseModel):
    """Search request parameters."""
    query: str
    mode: str = "hybrid"
    project: Optional[str] = None
    date_filter: Optional[str] = None


class ResumeRequest(BaseModel):
    """Session resume request."""
    conversation_id: str


class BackupCreateRequest(BaseModel):
    """Backup creation request."""
    backup_name: Optional[str] = None


class BackupRestoreRequest(BaseModel):
    """Backup restore request."""
    backup_name: str


class ChatRequest(BaseModel):
    """Chat request parameters."""
    query: str
    model_provider: str = "ollama"
    model_name: Optional[str] = None
