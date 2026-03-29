"""Tests for Phase 3 read path cutover: DuckDB default + parquet rollback."""
from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace

import duckdb
import pytest


def _create_duckdb_file(path: Path) -> None:
    """Create a valid empty DuckDB database file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = duckdb.connect(str(path))
    conn.close()


# ── Storage factory routing ──────────────────────────────────────


class TestBuildStorageServiceRouting:
    def test_returns_unified_storage_when_backend_duckdb_and_file_exists(
        self, tmp_path: Path
    ) -> None:
        from searchat.services.storage_service import build_storage_service

        db_path = tmp_path / "data" / "searchat.duckdb"
        _create_duckdb_file(db_path)

        cfg = SimpleNamespace(
            storage=SimpleNamespace(
                backend="duckdb",
                resolve_duckdb_path=lambda _sd: db_path,
                hnsw_ef_construction=128,
                hnsw_ef_search=64,
                hnsw_m=16,
            ),
            performance=SimpleNamespace(memory_limit_mb=None),
        )

        store = build_storage_service(tmp_path, config=cfg)
        from searchat.storage.unified_storage import UnifiedStorage

        assert isinstance(store, UnifiedStorage)

    def test_creates_database_when_duckdb_file_missing(
        self, tmp_path: Path
    ) -> None:
        from searchat.services.storage_service import build_storage_service

        db_path = tmp_path / "data" / "searchat.duckdb"
        # Deliberately do NOT create the file

        cfg = SimpleNamespace(
            storage=SimpleNamespace(
                backend="duckdb",
                resolve_duckdb_path=lambda _sd: db_path,
                hnsw_ef_construction=128,
                hnsw_ef_search=64,
                hnsw_m=16,
            ),
            performance=SimpleNamespace(memory_limit_mb=None),
        )

        store = build_storage_service(tmp_path, config=cfg)
        from searchat.storage.unified_storage import UnifiedStorage

        assert isinstance(store, UnifiedStorage)
        assert db_path.exists()


# ── Retrieval factory routing ────────────────────────────────────


class TestBuildRetrievalServiceRouting:
    def test_default_engine_returns_unified_search(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from searchat.services.retrieval_service import build_retrieval_service

        created: list[tuple[Path, object]] = []

        class FakeUnifiedSearchEngine:
            def __init__(self, search_dir: Path, config: object) -> None:
                created.append((search_dir, config))

        monkeypatch.setitem(
            sys.modules,
            "searchat.core.unified_search",
            SimpleNamespace(UnifiedSearchEngine=FakeUnifiedSearchEngine),
        )

        cfg = SimpleNamespace(search=SimpleNamespace(engine="unified"))
        store = build_retrieval_service(tmp_path, config=cfg)
        assert isinstance(store, FakeUnifiedSearchEngine)
        assert created == [(tmp_path, cfg)]



# ── Config defaults verify new values ────────────────────────────


class TestConfigDefaults:
    def test_default_storage_backend_is_duckdb(self) -> None:
        from searchat.config.constants import DEFAULT_STORAGE_BACKEND

        assert DEFAULT_STORAGE_BACKEND == "duckdb"

    def test_default_search_engine_is_unified(self) -> None:
        from searchat.config.constants import DEFAULT_SEARCH_ENGINE

        assert DEFAULT_SEARCH_ENGINE == "unified"

    def test_storage_config_defaults_to_duckdb(self) -> None:
        from searchat.config.settings import StorageConfig

        cfg = StorageConfig.from_dict({})
        assert cfg.backend == "duckdb"

    def test_search_config_defaults_to_unified(self) -> None:
        from searchat.config.settings import SearchConfig

        cfg = SearchConfig.from_dict({})
        assert cfg.engine == "unified"

    def test_storage_config_respects_explicit_parquet(self) -> None:
        from searchat.config.settings import StorageConfig

        cfg = StorageConfig.from_dict({"backend": "parquet"})
        assert cfg.backend == "parquet"

    def test_search_config_respects_explicit_legacy(self) -> None:
        from searchat.config.settings import SearchConfig

        cfg = SearchConfig.from_dict({"engine": "legacy"})
        assert cfg.engine == "legacy"
