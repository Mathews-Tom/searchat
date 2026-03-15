"""Retrieval-facing service contracts and construction helpers."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

from searchat.config import Config
from searchat.models import SearchFilters, SearchMode, SearchResults


class RetrievalService(Protocol):
    """Minimal retrieval contract for archive-backed search workflows."""

    def search(self, query: str, mode: SearchMode, filters: SearchFilters) -> SearchResults:
        """Execute a search against the conversation archive."""


@dataclass(frozen=True)
class SemanticVectorHit:
    """Semantic nearest-neighbor hit returned from vector search."""

    vector_id: int
    distance: float


class SemanticRetrievalService(RetrievalService, Protocol):
    """Retrieval contract for callers that also need semantic readiness access."""

    metadata_path: Path
    conversations_glob: str

    def ensure_semantic_ready(self) -> None:
        """Ensure metadata, FAISS, and embedding models are ready for semantic search."""

    def find_similar_vector_hits(self, text: str, k: int) -> list[SemanticVectorHit]:
        """Search the semantic index for nearest-neighbor vector hits."""

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
