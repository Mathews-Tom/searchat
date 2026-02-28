"""Additional tests for api/dependencies.py — warmup, snapshot, and singleton paths."""
from __future__ import annotations

import sys
import types
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

import searchat.api.dependencies as deps


@pytest.fixture(autouse=True)
def _reset_singletons(monkeypatch: pytest.MonkeyPatch) -> None:
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
    monkeypatch.setattr(deps, "_expertise_store", None)
    monkeypatch.setattr(deps, "_knowledge_graph_store", None)
    monkeypatch.setattr(deps, "_duckdb_store_by_dir", {})
    monkeypatch.setattr(deps, "_search_engine_by_dir", {})
    monkeypatch.setattr(deps, "_warmup_task", None)
    monkeypatch.setattr(deps, "projects_cache", "x")
    monkeypatch.setattr(deps, "projects_summary_cache", "x")
    monkeypatch.setattr(deps, "stats_cache", "x")


class FakeReadiness:
    def __init__(self) -> None:
        self.components: dict[str, str] = {}
        self.errors: dict[str, str] = {}
        self.warmup_started = False

    def set_component(self, name: str, status: str, *, error: str | None = None) -> None:
        self.components[name] = status
        if error is not None:
            self.errors[name] = error

    def mark_warmup_started(self) -> None:
        self.warmup_started = True

    def snapshot(self):
        return SimpleNamespace(components=dict(self.components))


# ── Snapshot validation ──────────────────────────────────────────


class TestIsValidSnapshotName:
    def test_empty_string(self):
        assert deps._is_valid_snapshot_name("") is False

    def test_dot(self):
        assert deps._is_valid_snapshot_name(".") is False

    def test_dotdot(self):
        assert deps._is_valid_snapshot_name("..") is False

    def test_slash(self):
        assert deps._is_valid_snapshot_name("foo/bar") is False

    def test_backslash(self):
        assert deps._is_valid_snapshot_name("foo\\bar") is False

    def test_contains_dotdot(self):
        assert deps._is_valid_snapshot_name("foo..bar") is False

    def test_valid_name(self):
        assert deps._is_valid_snapshot_name("backup_20250101_120000") is True

    def test_valid_with_dot(self):
        assert deps._is_valid_snapshot_name("v1.2.3") is True


# ── Getters raise when not initialized ───────────────────────────


class TestGetterErrors:
    def test_get_expertise_store_raises(self):
        with pytest.raises(RuntimeError, match="Expertise store not initialized"):
            deps.get_expertise_store()

    def test_get_knowledge_graph_store_raises(self):
        with pytest.raises(RuntimeError, match="Knowledge graph store not initialized"):
            deps.get_knowledge_graph_store()

    def test_get_bookmarks_service_raises(self):
        with pytest.raises(RuntimeError, match="Services not initialized"):
            deps.get_bookmarks_service()

    def test_get_saved_queries_service_raises(self):
        with pytest.raises(RuntimeError, match="Services not initialized"):
            deps.get_saved_queries_service()

    def test_get_dashboards_service_raises(self):
        with pytest.raises(RuntimeError, match="Services not initialized"):
            deps.get_dashboards_service()

    def test_get_analytics_service_raises(self):
        with pytest.raises(RuntimeError, match="Services not initialized"):
            deps.get_analytics_service()

    def test_get_backup_manager_raises(self):
        with pytest.raises(RuntimeError, match="Services not initialized"):
            deps.get_backup_manager()

    def test_get_duckdb_store_raises(self):
        with pytest.raises(RuntimeError, match="Services not initialized"):
            deps.get_duckdb_store()


# ── DuckDB store for alternate directories ───────────────────────


class TestGetDuckdbStoreFor:
    def test_returns_main_store_for_same_dir(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
        monkeypatch.setattr(deps, "_config", object())
        monkeypatch.setattr(deps, "_search_dir", tmp_path)
        monkeypatch.setattr(deps, "_duckdb_store", "MAIN")

        assert deps.get_duckdb_store_for(tmp_path) == "MAIN"

    def test_creates_store_for_other_dir(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
        other = tmp_path / "other"
        other.mkdir()
        monkeypatch.setattr(deps, "_config", SimpleNamespace(performance=SimpleNamespace(memory_limit_mb=128)))
        monkeypatch.setattr(deps, "_search_dir", tmp_path)
        monkeypatch.setattr(deps, "_duckdb_store", "MAIN")

        class _FakeStore:
            def __init__(self, path, *, memory_limit_mb):
                self.path = path

        monkeypatch.setitem(sys.modules, "searchat.api.duckdb_store", types.SimpleNamespace(DuckDBStore=_FakeStore))

        store = deps.get_duckdb_store_for(other)
        assert store.path == other

        # Second call returns cached
        assert deps.get_duckdb_store_for(other) is store

    def test_caches_by_dir(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
        other = tmp_path / "alt"
        other.mkdir()
        monkeypatch.setattr(deps, "_config", SimpleNamespace(performance=SimpleNamespace(memory_limit_mb=128)))
        monkeypatch.setattr(deps, "_search_dir", tmp_path)
        monkeypatch.setattr(deps, "_duckdb_store", "MAIN")

        fake = MagicMock()
        monkeypatch.setattr(deps, "_duckdb_store_by_dir", {str(other): fake})

        assert deps.get_duckdb_store_for(other) is fake


# ── Search engine for alternate directories ──────────────────────


class TestGetOrCreateSearchEngineFor:
    def test_returns_main_engine_for_same_dir(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
        readiness = FakeReadiness()
        monkeypatch.setattr(deps, "get_readiness", lambda: readiness)
        monkeypatch.setattr(deps, "_config", object())
        monkeypatch.setattr(deps, "_search_dir", tmp_path)

        fake_engine = MagicMock()

        class _SE:
            def __init__(self, sd, cfg):
                pass

        monkeypatch.setitem(sys.modules, "searchat.core.search_engine", types.SimpleNamespace(SearchEngine=_SE))
        monkeypatch.setattr(deps, "_search_engine", fake_engine)

        result = deps.get_or_create_search_engine_for(tmp_path)
        assert result is fake_engine

    def test_creates_engine_for_other_dir(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
        other = tmp_path / "snap"
        other.mkdir()
        cfg = object()
        monkeypatch.setattr(deps, "_config", cfg)
        monkeypatch.setattr(deps, "_search_dir", tmp_path)
        monkeypatch.setattr(deps, "_duckdb_store", "MAIN")

        class _SE:
            def __init__(self, sd, config):
                self.sd = sd

        monkeypatch.setitem(sys.modules, "searchat.core.search_engine", types.SimpleNamespace(SearchEngine=_SE))

        engine = deps.get_or_create_search_engine_for(other)
        assert engine.sd == other

        # Cached
        assert deps.get_or_create_search_engine_for(other) is engine


# ── Warmup embedded model ────────────────────────────────────────


class TestWarmupEmbeddedModel:
    def test_skips_when_provider_not_embedded(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
        readiness = FakeReadiness()
        monkeypatch.setattr(deps, "get_readiness", lambda: readiness)
        cfg = SimpleNamespace(
            llm=SimpleNamespace(default_provider="openai"),
        )
        monkeypatch.setattr(deps, "_config", cfg)
        monkeypatch.setattr(deps, "_search_dir", tmp_path)

        deps._warmup_embedded_model()
        assert readiness.components["embedded_model"] == "idle"

    def test_ready_when_model_path_exists(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
        readiness = FakeReadiness()
        monkeypatch.setattr(deps, "get_readiness", lambda: readiness)

        model_file = tmp_path / "model.gguf"
        model_file.touch()

        cfg = SimpleNamespace(
            llm=SimpleNamespace(
                default_provider="embedded",
                embedded_model_path=str(model_file),
            ),
        )
        monkeypatch.setattr(deps, "_config", cfg)
        monkeypatch.setattr(deps, "_search_dir", tmp_path)

        deps._warmup_embedded_model()
        assert readiness.components["embedded_model"] == "ready"

    def test_returns_early_when_config_fails(self, monkeypatch: pytest.MonkeyPatch):
        readiness = FakeReadiness()
        monkeypatch.setattr(deps, "get_readiness", lambda: readiness)
        monkeypatch.setattr(deps, "_config", None)

        deps._warmup_embedded_model()
        assert "embedded_model" not in readiness.components


# ── Initialize services with expertise/KG ────────────────────────


class TestInitializeWithExpertise:
    def test_initializes_expertise_store_when_enabled(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
        readiness = FakeReadiness()
        monkeypatch.setattr(deps, "get_readiness", lambda: readiness)

        cfg = SimpleNamespace(
            performance=SimpleNamespace(memory_limit_mb=128),
            analytics=SimpleNamespace(enabled=False),
            paths=SimpleNamespace(search_directory=str(tmp_path)),
            expertise=SimpleNamespace(enabled=True),
            knowledge_graph=SimpleNamespace(enabled=False),
        )
        monkeypatch.setattr(deps.Config, "load", staticmethod(lambda: cfg))
        monkeypatch.setattr(deps.PathResolver, "get_shared_search_dir", staticmethod(lambda _: tmp_path))
        monkeypatch.setattr(deps, "BackupManager", lambda _: object())
        monkeypatch.setattr(deps, "PlatformManager", lambda: object())

        class _DuckDBStore:
            def __init__(self, path, *, memory_limit_mb):
                pass

            def validate_parquet_scan(self):
                pass

        class _ExpertiseStore:
            def __init__(self, path):
                self.path = path

        monkeypatch.setitem(sys.modules, "searchat.api.duckdb_store", types.SimpleNamespace(DuckDBStore=_DuckDBStore))
        monkeypatch.setitem(sys.modules, "searchat.services.bookmarks", types.SimpleNamespace(BookmarksService=lambda _: object()))
        monkeypatch.setitem(sys.modules, "searchat.services.saved_queries", types.SimpleNamespace(SavedQueriesService=lambda _: object()))
        monkeypatch.setitem(sys.modules, "searchat.services.dashboards", types.SimpleNamespace(DashboardsService=lambda _: object()))
        monkeypatch.setitem(sys.modules, "searchat.services.analytics", types.SimpleNamespace(SearchAnalyticsService=lambda _: object()))
        monkeypatch.setitem(sys.modules, "searchat.expertise.store", types.SimpleNamespace(ExpertiseStore=_ExpertiseStore))

        deps.initialize_services()

        store = deps.get_expertise_store()
        assert store.path == tmp_path

    def test_initializes_kg_store_when_enabled(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
        readiness = FakeReadiness()
        monkeypatch.setattr(deps, "get_readiness", lambda: readiness)

        cfg = SimpleNamespace(
            performance=SimpleNamespace(memory_limit_mb=128),
            analytics=SimpleNamespace(enabled=False),
            paths=SimpleNamespace(search_directory=str(tmp_path)),
            expertise=SimpleNamespace(enabled=False),
            knowledge_graph=SimpleNamespace(enabled=True),
        )
        monkeypatch.setattr(deps.Config, "load", staticmethod(lambda: cfg))
        monkeypatch.setattr(deps.PathResolver, "get_shared_search_dir", staticmethod(lambda _: tmp_path))
        monkeypatch.setattr(deps, "BackupManager", lambda _: object())
        monkeypatch.setattr(deps, "PlatformManager", lambda: object())

        class _DuckDBStore:
            def __init__(self, path, *, memory_limit_mb):
                pass

        class _KGStore:
            def __init__(self, path):
                self.path = path

        monkeypatch.setitem(sys.modules, "searchat.api.duckdb_store", types.SimpleNamespace(DuckDBStore=_DuckDBStore))
        monkeypatch.setitem(sys.modules, "searchat.services.bookmarks", types.SimpleNamespace(BookmarksService=lambda _: object()))
        monkeypatch.setitem(sys.modules, "searchat.services.saved_queries", types.SimpleNamespace(SavedQueriesService=lambda _: object()))
        monkeypatch.setitem(sys.modules, "searchat.services.dashboards", types.SimpleNamespace(DashboardsService=lambda _: object()))
        monkeypatch.setitem(sys.modules, "searchat.services.analytics", types.SimpleNamespace(SearchAnalyticsService=lambda _: object()))
        monkeypatch.setitem(sys.modules, "searchat.knowledge_graph", types.SimpleNamespace(KnowledgeGraphStore=_KGStore))

        deps.initialize_services()

        store = deps.get_knowledge_graph_store()
        assert store.path == tmp_path


# ── Trigger search engine warmup ─────────────────────────────────


class TestTriggerSearchEngineWarmup:
    def test_calls_start_background_warmup(self, monkeypatch: pytest.MonkeyPatch):
        called = {"count": 0}
        monkeypatch.setattr(deps, "start_background_warmup", lambda: called.__setitem__("count", called["count"] + 1))

        deps.trigger_search_engine_warmup()
        assert called["count"] == 1


# ── Resolve dataset search dir ───────────────────────────────────


class TestResolveDatasetSearchDir:
    def test_returns_main_dir_when_snapshot_none(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
        monkeypatch.setattr(deps, "_config", object())
        monkeypatch.setattr(deps, "_search_dir", tmp_path)

        search_dir, snap = deps.resolve_dataset_search_dir(None)
        assert search_dir == tmp_path
        assert snap is None

    def test_returns_main_dir_when_snapshot_empty(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
        monkeypatch.setattr(deps, "_config", object())
        monkeypatch.setattr(deps, "_search_dir", tmp_path)

        search_dir, snap = deps.resolve_dataset_search_dir("")
        assert search_dir == tmp_path
        assert snap is None

    def test_raises_when_snapshots_disabled(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
        monkeypatch.setattr(deps, "_config", SimpleNamespace(snapshots=SimpleNamespace(enabled=False)))
        monkeypatch.setattr(deps, "_search_dir", tmp_path)

        with pytest.raises(ValueError, match="Snapshot mode is disabled"):
            deps.resolve_dataset_search_dir("some_snap")

    def test_raises_for_invalid_snapshot_name(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
        monkeypatch.setattr(deps, "_config", SimpleNamespace(snapshots=SimpleNamespace(enabled=True)))
        monkeypatch.setattr(deps, "_search_dir", tmp_path)

        with pytest.raises(ValueError, match="Invalid snapshot name"):
            deps.resolve_dataset_search_dir("../../etc")
