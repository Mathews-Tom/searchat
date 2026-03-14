"""Retrieval-facing service contracts and construction helpers."""
from __future__ import annotations

from pathlib import Path
from typing import Any, Protocol

from searchat.config import Config
from searchat.models import SearchFilters, SearchMode, SearchResults


class RetrievalService(Protocol):
    """Minimal retrieval contract for archive-backed search workflows."""

    def search(self, query: str, mode: SearchMode, filters: SearchFilters) -> SearchResults:
        """Execute a search against the conversation archive."""


class SemanticRetrievalService(RetrievalService, Protocol):
    """Retrieval contract for callers that also need semantic readiness access."""

    metadata_path: Path
    conversations_glob: str
    faiss_index: Any | None
    embedder: Any | None

    def ensure_faiss_loaded(self) -> None:
        """Ensure the FAISS index is loaded."""

    def ensure_embedder_loaded(self) -> None:
        """Ensure the embedder is loaded."""

    def ensure_metadata_ready(self) -> None:
        """Ensure metadata is available for semantic queries."""

    def refresh_index(self) -> None:
        """Refresh internal retrieval caches and index structures."""


def build_retrieval_service(
    search_dir: Path,
    *,
    config: Config,
) -> SemanticRetrievalService:
    """Create the retrieval service for a dataset root."""
    from searchat.core.search_engine import SearchEngine

    return SearchEngine(search_dir, config)
