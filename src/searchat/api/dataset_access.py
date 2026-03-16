"""Dataset-scoped access helpers for API routes."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import searchat.api.dependencies as deps
from searchat.api.utils import check_semantic_readiness, resolve_dataset
from searchat.models import SearchMode
from searchat.services.retrieval_service import RetrievalService, SemanticRetrievalService
from searchat.services.storage_service import StorageService


@dataclass(frozen=True)
class DatasetStoreContext:
    search_dir: Path
    snapshot_name: str | None
    store: StorageService


@dataclass(frozen=True)
class DatasetRetrievalContext:
    search_dir: Path
    snapshot_name: str | None
    retrieval_service: RetrievalService


def get_dataset_store(snapshot: str | None) -> DatasetStoreContext:
    """Resolve dataset-scoped storage access for a route request."""
    search_dir, snapshot_name = resolve_dataset(snapshot)
    if snapshot_name is None:
        store = deps.get_duckdb_store()
    else:
        store = deps.get_duckdb_store_for(search_dir)
    return DatasetStoreContext(search_dir=search_dir, snapshot_name=snapshot_name, store=store)


def get_dataset_retrieval(
    snapshot: str | None,
    *,
    search_mode: SearchMode,
) -> DatasetRetrievalContext:
    """Resolve dataset-scoped retrieval access for a route request."""
    search_dir, snapshot_name = resolve_dataset(snapshot)

    if snapshot_name is not None:
        retrieval_service = deps.get_or_create_search_engine_for(search_dir)
    elif search_mode == SearchMode.KEYWORD:
        retrieval_service = deps.get_or_create_search_engine()
    else:
        not_ready = check_semantic_readiness(retrieval_service=deps.get_search_engine)
        if not_ready is not None:
            raise _DatasetNotReady(not_ready)
        retrieval_service = deps.get_search_engine()

    return DatasetRetrievalContext(
        search_dir=search_dir,
        snapshot_name=snapshot_name,
        retrieval_service=retrieval_service,
    )


def get_dataset_semantic_retrieval(snapshot: str | None) -> tuple[DatasetStoreContext, SemanticRetrievalService]:
    """Resolve dataset-scoped storage and semantic retrieval access."""
    store_context = get_dataset_store(snapshot)
    if store_context.snapshot_name is None:
        retrieval_service = deps.get_search_engine()
    else:
        retrieval_service = deps.get_or_create_search_engine_for(store_context.search_dir)
    return store_context, retrieval_service


class _DatasetNotReady(RuntimeError):
    """Internal sentinel for returning readiness responses from route helpers."""

    def __init__(self, response) -> None:
        super().__init__("Dataset retrieval is not ready")
        self.response = response
