"""IndexingBackend protocol — abstraction seam for conversation indexing."""
from __future__ import annotations

from typing import Protocol

from searchat.core.progress import ProgressCallback
from searchat.models import IndexStats, UpdateStats


class IndexingBackend(Protocol):
    """Structural contract for conversation indexing operations.

    V1 methods map to ConversationIndexer (Parquet+FAISS).
    V2 stub (index_from_source_files) will be implemented by the
    unified indexer in Phase 5.
    """

    # -- V1: current ConversationIndexer methods --

    def index_all(
        self,
        force: bool = False,
        progress: ProgressCallback | None = None,
    ) -> IndexStats: ...

    def index_append_only(
        self,
        file_paths: list[str],
        progress: ProgressCallback | None = None,
    ) -> UpdateStats: ...

    def get_indexed_file_paths(self) -> set: ...
