from __future__ import annotations

import asyncio
import sys
import types
from pathlib import Path
from types import SimpleNamespace

import pytest

import searchat.api.dependencies as deps


class FakeReadiness:
    def __init__(self) -> None:
        self.components: dict[str, str] = {}
        self.errors: dict[str, str] = {}
        self.warmup_started = False
        self.component_calls: list[tuple[str, str, str | None]] = []

    def set_component(self, name: str, status: str, *, error: str | None = None) -> None:
        self.components[name] = status
        if error is not None:
            self.errors[name] = error
        self.component_calls.append((name, status, error))

    def mark_warmup_started(self) -> None:
        self.warmup_started = True

    def snapshot(self):
        return SimpleNamespace(components=dict(self.components))


@pytest.fixture(autouse=True)
def reset_dependency_singletons(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(deps, "_config", None)
    monkeypatch.setattr(deps, "_search_dir", None)
    monkeypatch.setattr(deps, "_search_engine", None)
    monkeypatch.setattr(deps, "_indexer", None)
    monkeypatch.setattr(deps, "_backup_manager", None)
    monkeypatch.setattr(deps, "_platform_manager", None)
    monkeypatch.setattr(deps, "_bookmarks_service", None)
    monkeypatch.setattr(deps, "_saved_queries_service", None)
    monkeypatch.setattr(deps, "_dashboards_service", None)
    monkeypatch.setattr(deps, "_analytics_service", None)
    monkeypatch.setattr(deps, "_watcher", None)
    monkeypatch.setattr(deps, "_duckdb_store", None)
    monkeypatch.setattr(deps, "_duckdb_store_by_dir", {})
    monkeypatch.setattr(deps, "_search_engine_by_dir", {})
    monkeypatch.setattr(deps, "_warmup_task", None)

    monkeypatch.setattr(deps, "projects_cache", "x")
    monkeypatch.setattr(deps, "projects_summary_cache", "x")
    monkeypatch.setattr(deps, "stats_cache", "x")


def test_initialize_services_sets_components_ready(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    readiness = FakeReadiness()
    monkeypatch.setattr(deps, "get_readiness", lambda: readiness)

    cfg = SimpleNamespace(
        performance=SimpleNamespace(memory_limit_mb=123),
        analytics=SimpleNamespace(enabled=False),
        paths=SimpleNamespace(search_directory=str(tmp_path)),
        expertise=SimpleNamespace(enabled=False),
        knowledge_graph=SimpleNamespace(enabled=False),
    )
    monkeypatch.setattr(deps.Config, "load", staticmethod(lambda: cfg))
    monkeypatch.setattr(deps.PathResolver, "get_shared_search_dir", staticmethod(lambda _cfg: tmp_path))

    monkeypatch.setattr(deps, "BackupManager", lambda _p: object())
    monkeypatch.setattr(deps, "PlatformManager", lambda: object())

    class _DuckDBStore:
        def __init__(self, path: Path, *, memory_limit_mb: int):
            self.path = path
            self.memory_limit_mb: int = memory_limit_mb

        def validate_parquet_scan(self) -> None:
            return None

    class _BookmarksService:
        def __init__(self, _cfg):
            self.cfg = _cfg

    class _SavedQueriesService:
        def __init__(self, _cfg):
            self.cfg = _cfg

    class _DashboardsService:
        def __init__(self, _cfg):
            self.cfg = _cfg

    class _AnalyticsService:
        def __init__(self, _cfg):
            self.cfg = _cfg

    monkeypatch.setitem(sys.modules, "searchat.api.duckdb_store", types.SimpleNamespace(DuckDBStore=_DuckDBStore))
    monkeypatch.setitem(sys.modules, "searchat.services.bookmarks", types.SimpleNamespace(BookmarksService=_BookmarksService))
    monkeypatch.setitem(sys.modules, "searchat.services.saved_queries", types.SimpleNamespace(SavedQueriesService=_SavedQueriesService))
    monkeypatch.setitem(sys.modules, "searchat.services.dashboards", types.SimpleNamespace(DashboardsService=_DashboardsService))
    monkeypatch.setitem(sys.modules, "searchat.services.analytics", types.SimpleNamespace(SearchAnalyticsService=_AnalyticsService))

    deps.initialize_services()

    assert deps.get_config() is cfg
    assert deps.get_search_dir() == tmp_path
    assert deps.get_backup_manager() is not None
    assert deps.get_platform_manager() is not None
    assert getattr(deps.get_duckdb_store(), "memory_limit_mb") == 123
    assert deps.get_bookmarks_service() is not None
    assert deps.get_saved_queries_service() is not None
    assert deps.get_dashboards_service() is not None
    assert deps.get_analytics_service() is not None

    assert readiness.components["services"] == "ready"


def test_initialize_services_sets_error_on_exception(monkeypatch: pytest.MonkeyPatch) -> None:
    readiness = FakeReadiness()
    monkeypatch.setattr(deps, "get_readiness", lambda: readiness)

    def _boom():
        raise RuntimeError("boom")

    monkeypatch.setattr(deps.Config, "load", staticmethod(_boom))

    with pytest.raises(RuntimeError, match="boom"):
        deps.initialize_services()

    assert readiness.components["services"] == "error"


def test_start_background_warmup_returns_if_not_initialized(monkeypatch: pytest.MonkeyPatch) -> None:
    readiness = FakeReadiness()
    monkeypatch.setattr(deps, "get_readiness", lambda: readiness)

    deps.start_background_warmup()

    assert readiness.warmup_started is False


def test_start_background_warmup_returns_without_event_loop(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    readiness = FakeReadiness()
    monkeypatch.setattr(deps, "get_readiness", lambda: readiness)

    monkeypatch.setattr(deps, "_config", object())
    monkeypatch.setattr(deps, "_search_dir", tmp_path)

    monkeypatch.setattr(asyncio, "get_running_loop", lambda: (_ for _ in ()).throw(RuntimeError("no loop")))

    deps.start_background_warmup()

    assert readiness.warmup_started is True


def test_start_background_warmup_is_idempotent(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    readiness = FakeReadiness()
    monkeypatch.setattr(deps, "get_readiness", lambda: readiness)

    monkeypatch.setattr(deps, "_config", object())
    monkeypatch.setattr(deps, "_search_dir", tmp_path)

    class _Task:
        def done(self) -> bool:
            return False

    class _Loop:
        def __init__(self) -> None:
            self.created = False

        def create_task(self, _coro):
            self.created = True
            return object()

    loop = _Loop()
    monkeypatch.setattr(asyncio, "get_running_loop", lambda: loop)
    monkeypatch.setattr(deps, "_warmup_task", _Task())

    deps.start_background_warmup()

    assert loop.created is False


def test_warmup_duckdb_parquet_success(monkeypatch: pytest.MonkeyPatch) -> None:
    readiness = FakeReadiness()
    monkeypatch.setattr(deps, "get_readiness", lambda: readiness)

    class _Store:
        def validate_parquet_scan(self) -> None:
            return None

    monkeypatch.setattr(deps, "get_duckdb_store", lambda: _Store())
    monkeypatch.setenv("SEARCHAT_PROFILE_WARMUP", "1")

    deps._warmup_duckdb_parquet()

    assert readiness.components["duckdb"] == "ready"
    assert readiness.components["parquet"] == "ready"


def test_warmup_duckdb_parquet_failure_sets_error(monkeypatch: pytest.MonkeyPatch) -> None:
    readiness = FakeReadiness()
    monkeypatch.setattr(deps, "get_readiness", lambda: readiness)

    class _Store:
        def validate_parquet_scan(self) -> None:
            raise RuntimeError("bad parquet")

    monkeypatch.setattr(deps, "get_duckdb_store", lambda: _Store())

    deps._warmup_duckdb_parquet()

    assert readiness.components["duckdb"] == "error"
    assert readiness.components["parquet"] == "error"


def test_warmup_semantic_components_success(monkeypatch: pytest.MonkeyPatch) -> None:
    readiness = FakeReadiness()
    monkeypatch.setattr(deps, "get_readiness", lambda: readiness)

    class _Engine:
        def ensure_metadata_ready(self) -> None:
            return None

        def ensure_faiss_loaded(self) -> None:
            return None

        def ensure_embedder_loaded(self) -> None:
            return None

    monkeypatch.setattr(deps, "_ensure_search_engine", lambda: _Engine())
    monkeypatch.setenv("SEARCHAT_PROFILE_WARMUP", "1")

    deps._warmup_semantic_components()

    assert readiness.components["metadata"] == "ready"
    assert readiness.components["faiss"] == "ready"
    assert readiness.components["embedder"] == "ready"


def test_warmup_semantic_components_failure_marks_unready_components_error(monkeypatch: pytest.MonkeyPatch) -> None:
    readiness = FakeReadiness()
    monkeypatch.setattr(deps, "get_readiness", lambda: readiness)

    class _Engine:
        def ensure_metadata_ready(self) -> None:
            return None

        def ensure_faiss_loaded(self) -> None:
            raise RuntimeError("faiss boom")

        def ensure_embedder_loaded(self) -> None:
            return None

    monkeypatch.setattr(deps, "_ensure_search_engine", lambda: _Engine())

    deps._warmup_semantic_components()

    assert readiness.components["metadata"] == "ready"
    assert readiness.components["faiss"] == "error"
    assert readiness.components["embedder"] == "error"


def test_invalidate_search_index_clears_caches_and_marks_idle(monkeypatch: pytest.MonkeyPatch) -> None:
    readiness = FakeReadiness()
    monkeypatch.setattr(deps, "get_readiness", lambda: readiness)

    called = {"refresh": 0, "warmup": 0}

    class _Engine:
        def refresh_index(self) -> None:
            called["refresh"] += 1

    monkeypatch.setattr(deps, "_search_engine", _Engine())
    monkeypatch.setattr(deps, "start_background_warmup", lambda: called.__setitem__("warmup", called["warmup"] + 1))

    deps.invalidate_search_index()

    assert deps.projects_cache is None
    assert deps.projects_summary_cache is None
    assert deps.stats_cache is None
    assert called["refresh"] == 1
    assert readiness.components["metadata"] == "idle"
    assert readiness.components["faiss"] == "idle"
    assert readiness.components["embedder"] == "idle"
    assert called["warmup"] == 1


def test_get_search_engine_raises_when_not_ready(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr(deps, "_config", object())
    monkeypatch.setattr(deps, "_search_dir", tmp_path)
    monkeypatch.setattr(deps, "_search_engine", None)

    with pytest.raises(RuntimeError, match="Search engine not ready"):
        deps.get_search_engine()


def test_get_indexer_creates_lazily(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr(deps, "_config", object())
    monkeypatch.setattr(deps, "_search_dir", tmp_path)

    def _ensure() -> str:
        deps._indexer = "IDX"
        return "IDX"

    monkeypatch.setattr(deps, "_ensure_indexer", _ensure)

    assert deps.get_indexer() == "IDX"


def test_ensure_search_engine_creates_instance(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    readiness = FakeReadiness()
    monkeypatch.setattr(deps, "get_readiness", lambda: readiness)

    cfg = object()
    monkeypatch.setattr(deps, "_config", cfg)
    monkeypatch.setattr(deps, "_search_dir", tmp_path)

    class _SearchEngine:
        def __init__(self, search_dir: Path, config):
            self.search_dir = search_dir
            self.config = config

    monkeypatch.setitem(sys.modules, "searchat.core.search_engine", types.SimpleNamespace(SearchEngine=_SearchEngine))

    engine = deps._ensure_search_engine()
    assert engine.search_dir == tmp_path
    assert engine.config is cfg
    assert readiness.components["search_engine"] == "ready"


def test_ensure_search_engine_sets_error_on_failure(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    readiness = FakeReadiness()
    monkeypatch.setattr(deps, "get_readiness", lambda: readiness)

    monkeypatch.setattr(deps, "_config", object())
    monkeypatch.setattr(deps, "_search_dir", tmp_path)

    class _SearchEngine:
        def __init__(self, _search_dir: Path, _config):
            raise RuntimeError("init failed")

    monkeypatch.setitem(sys.modules, "searchat.core.search_engine", types.SimpleNamespace(SearchEngine=_SearchEngine))

    with pytest.raises(RuntimeError, match="init failed"):
        deps._ensure_search_engine()

    assert readiness.components["search_engine"] == "error"


def test_ensure_indexer_creates_instance(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    readiness = FakeReadiness()
    monkeypatch.setattr(deps, "get_readiness", lambda: readiness)

    cfg = object()
    monkeypatch.setattr(deps, "_config", cfg)
    monkeypatch.setattr(deps, "_search_dir", tmp_path)

    class _Indexer:
        def __init__(self, search_dir: Path, config):
            self.search_dir = search_dir
            self.config = config

    monkeypatch.setitem(sys.modules, "searchat.core.indexer", types.SimpleNamespace(ConversationIndexer=_Indexer))

    idx = deps._ensure_indexer()
    assert idx.search_dir == tmp_path
    assert idx.config is cfg
    assert readiness.components["indexer"] == "ready"


def test_ensure_indexer_sets_error_on_failure(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    readiness = FakeReadiness()
    monkeypatch.setattr(deps, "get_readiness", lambda: readiness)

    monkeypatch.setattr(deps, "_config", object())
    monkeypatch.setattr(deps, "_search_dir", tmp_path)

    class _Indexer:
        def __init__(self, _search_dir: Path, _config):
            raise RuntimeError("indexer boom")

    monkeypatch.setitem(sys.modules, "searchat.core.indexer", types.SimpleNamespace(ConversationIndexer=_Indexer))

    with pytest.raises(RuntimeError, match="indexer boom"):
        deps._ensure_indexer()

    assert readiness.components["indexer"] == "error"
