"""RetrievalBackend protocol — abstraction seam for search/retrieval."""
from __future__ import annotations

from pathlib import Path
from typing import Protocol

from searchat.models import SearchFilters, SearchMode, SearchResults
from searchat.services.retrieval_service import (
    RetrievalCapabilities,
    SemanticVectorHit,
)


class RetrievalBackend(Protocol):
    """Structural contract for retrieval and search operations.

    V1 methods map to the current SearchEngine (SemanticRetrievalService).
    V2 stubs (adaptive, cross_layer, distill) will be wired in Phase 2.
    """

    metadata_path: Path
    conversations_glob: str

    # -- V1: current SemanticRetrievalService methods --

    def search(
        self, query: str, mode: SearchMode, filters: SearchFilters
    ) -> SearchResults: ...

    def ensure_semantic_ready(self) -> None: ...

    def find_similar_vector_hits(
        self, text: str, k: int
    ) -> list[SemanticVectorHit]: ...

    def describe_capabilities(self) -> RetrievalCapabilities: ...

    def refresh_index(self) -> None: ...
