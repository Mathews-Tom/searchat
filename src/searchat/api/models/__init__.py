"""Pydantic models for API requests and responses."""
from searchat.api.models.requests import (
    SearchRequest,
    ResumeRequest,
    BackupCreateRequest,
    BackupRestoreRequest,
    ChatRequest,
    ChatRagRequest,
)
from searchat.api.models.responses import (
    SearchResultResponse,
    ConversationMessage,
    ConversationResponse,
    BackupMetadataResponse,
    BackupCreateResponse,
    BackupListResponse,
    BackupRestoreResponse,
    ConversationSource,
    RAGResponse,
    CodeSearchResultResponse,
    CodeSearchResponse,
)

__all__ = [
    # Requests
    "SearchRequest",
    "ResumeRequest",
    "BackupCreateRequest",
    "BackupRestoreRequest",
    "ChatRequest",
    "ChatRagRequest",
    # Responses
    "SearchResultResponse",
    "ConversationMessage",
    "ConversationResponse",
    "BackupMetadataResponse",
    "BackupCreateResponse",
    "BackupListResponse",
    "BackupRestoreResponse",
    "ConversationSource",
    "RAGResponse",
    "CodeSearchResultResponse",
    "CodeSearchResponse",
]
