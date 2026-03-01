"""Pydantic request models for API endpoints."""
from __future__ import annotations

from pydantic import BaseModel, Field


class ResumeRequest(BaseModel):
    """Session resume request."""
    conversation_id: str


class ChatRequest(BaseModel):
    """Chat request parameters."""
    query: str
    model_provider: str = "ollama"
    model_name: str | None = None
    session_id: str | None = None


class ChatRagRequest(BaseModel):
    """Chat request for non-streaming RAG response."""

    query: str
    model_provider: str = "ollama"
    model_name: str | None = None
    session_id: str | None = None

    temperature: float | None = Field(default=None, ge=0.0, le=2.0)
    max_tokens: int | None = Field(default=None, ge=1, le=32768)
    system_prompt: str | None = Field(default=None, max_length=8000)
