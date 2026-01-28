"""Pydantic request models for API endpoints."""
from __future__ import annotations

from pydantic import BaseModel


class SearchRequest(BaseModel):
    """Search request parameters."""
    query: str
    mode: str = "hybrid"
    project: str | None = None
    date_filter: str | None = None


class ResumeRequest(BaseModel):
    """Session resume request."""
    conversation_id: str


class BackupCreateRequest(BaseModel):
    """Backup creation request."""
    backup_name: str | None = None


class BackupRestoreRequest(BaseModel):
    """Backup restore request."""
    backup_name: str


class ChatRequest(BaseModel):
    """Chat request parameters."""
    query: str
    model_provider: str = "ollama"
    model_name: str | None = None
