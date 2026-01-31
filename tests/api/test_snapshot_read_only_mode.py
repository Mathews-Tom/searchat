from __future__ import annotations

from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

import searchat.api.dependencies as deps
from searchat.api.duckdb_store import DuckDBStore
from searchat.api.routers import backup as backup_router
from searchat.api.routers import conversations as conversations_router
from searchat.api.routers import indexing as indexing_router
from searchat.api.routers import search as search_router
from searchat.config import Config
from searchat.core.indexer import ConversationIndexer
from searchat.core.progress import LoggingProgressAdapter
from searchat.services.backup import BackupManager
from searchat.config.constants import (
    INDEX_FORMAT,
    INDEX_FORMAT_VERSION,
    INDEX_METADATA_FILENAME,
    INDEX_SCHEMA_VERSION,
)
from searchat.models.schemas import METADATA_SCHEMA


@pytest.fixture
def app_no_startup() -> FastAPI:
    app = FastAPI()
    app.include_router(search_router.router, prefix="/api")
    app.include_router(conversations_router.router, prefix="/api")
    app.include_router(indexing_router.router, prefix="/api")
    app.include_router(backup_router.router, prefix="/api/backup")
    return app


@pytest.fixture
def client(app_no_startup: FastAPI) -> TestClient:
    return TestClient(app_no_startup)


def _init_deps_for_search_dir(search_dir: Path) -> None:
    cfg = Config.load()
    deps._config = cfg
    deps._search_dir = search_dir
    deps._backup_manager = BackupManager(search_dir)
    deps._duckdb_store = DuckDBStore(search_dir, memory_limit_mb=cfg.performance.memory_limit_mb)

    # Clear caches
    deps.projects_cache = None
    deps.projects_summary_cache = None
    deps.stats_cache = None
    deps._duckdb_store_by_dir = {}
    deps._search_engine_by_dir = {}


def _bootstrap_empty_index(search_dir: Path, cfg: Config) -> None:
    """Create minimal on-disk index artifacts so append-only indexing can run."""
    indices_dir = search_dir / "data" / "indices"
    indices_dir.mkdir(parents=True, exist_ok=True)

    metadata_path = indices_dir / INDEX_METADATA_FILENAME
    from datetime import datetime

    metadata = {
        "embedding_model": cfg.embedding.model,
        "format": INDEX_FORMAT,
        "schema_version": INDEX_SCHEMA_VERSION,
        "index_format_version": INDEX_FORMAT_VERSION,
        "created_at": datetime.now().isoformat(),
        "total_conversations": 0,
        "total_chunks": 0,
        "next_vector_id": 0,
    }
    metadata_path.write_text(__import__("json").dumps(metadata, indent=2), encoding="utf-8")

    # Empty embeddings metadata parquet.
    import pyarrow as pa
    import pyarrow.parquet as pq

    empty_table = pa.Table.from_pylist([], schema=METADATA_SCHEMA)
    pq.write_table(empty_table, indices_dir / "embeddings.metadata.parquet")

    # Placeholder FAISS file (faiss module is mocked in tests).
    (indices_dir / "embeddings.faiss").write_bytes(b"")


def test_snapshot_projects_and_conversation_view_use_backup_dataset(
    client: TestClient,
    temp_search_dir: Path,
    sample_claude_conversation: Path,
):
    _init_deps_for_search_dir(temp_search_dir)

    cfg = deps.get_config()
    _bootstrap_empty_index(temp_search_dir, cfg)
    indexer = ConversationIndexer(temp_search_dir, cfg)
    stats = indexer.index_append_only([str(sample_claude_conversation)], LoggingProgressAdapter())
    assert stats.new_conversations == 1

    store = deps.get_duckdb_store()
    conv_rows = store.list_conversations(limit=10)
    assert conv_rows
    conversation_id = conv_rows[0]["conversation_id"]

    backup_manager = deps.get_backup_manager()
    meta = backup_manager.create_backup()
    snapshot_name = meta.backup_path.name

    # Delete source file to ensure snapshot view does not depend on it.
    sample_claude_conversation.unlink()

    # Active dataset should work.
    resp_active = client.get("/api/projects/summary")
    assert resp_active.status_code == 200
    assert isinstance(resp_active.json(), list)

    # Snapshot dataset should also work.
    resp_snapshot = client.get(f"/api/projects/summary?snapshot={snapshot_name}")
    assert resp_snapshot.status_code == 200
    assert isinstance(resp_snapshot.json(), list)

    conv_resp = client.get(f"/api/conversation/{conversation_id}?snapshot={snapshot_name}")
    assert conv_resp.status_code == 200
    payload = conv_resp.json()
    assert payload["conversation_id"] == conversation_id
    assert isinstance(payload.get("messages"), list)
    assert len(payload["messages"]) > 0


def test_snapshot_mode_blocks_write_endpoints(
    client: TestClient,
    temp_search_dir: Path,
    sample_claude_conversation: Path,
):
    _init_deps_for_search_dir(temp_search_dir)

    cfg = deps.get_config()
    _bootstrap_empty_index(temp_search_dir, cfg)
    indexer = ConversationIndexer(temp_search_dir, cfg)
    indexer.index_append_only([str(sample_claude_conversation)], LoggingProgressAdapter())

    backup_manager = deps.get_backup_manager()
    meta = backup_manager.create_backup()
    snapshot_name = meta.backup_path.name

    resp = client.post(f"/api/index_missing?snapshot={snapshot_name}")
    assert resp.status_code == 403

    resp = client.post(f"/api/backup/create?snapshot={snapshot_name}")
    assert resp.status_code == 403

    resp = client.post(
        f"/api/resume?snapshot={snapshot_name}",
        json={"conversation_id": "does-not-matter"},
    )
    assert resp.status_code == 403
