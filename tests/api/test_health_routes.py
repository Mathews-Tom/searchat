from __future__ import annotations

import importlib
import shutil
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from searchat.api import state as api_state


def _reset_readiness() -> None:
    from searchat.api.readiness import get_readiness

    r = get_readiness()
    snap = r.snapshot()
    for name in snap.components:
        r.set_component(name, "idle")
    r.set_watcher("disabled")


def _api_app_module():
    return importlib.import_module("searchat.api.app")


@pytest.fixture(autouse=True)
def _reset_dependencies_singletons(monkeypatch: pytest.MonkeyPatch) -> None:
    import searchat.api.dependencies as deps

    deps._config = None
    deps._search_dir = None
    deps._search_engine = None
    deps._indexer = None
    deps._backup_manager = None
    deps._platform_manager = None
    deps._watcher = None
    deps._duckdb_store = None
    deps._duckdb_store_by_dir.clear()
    deps._search_engine_by_dir.clear()
    api_state.reset_runtime_state()
    _reset_readiness()


# ---------------------------------------------------------------------------
# /api/health/live
# ---------------------------------------------------------------------------


def test_health_live_always_200() -> None:
    mod = _api_app_module()
    client = TestClient(mod.app, raise_server_exceptions=False)
    resp = client.get("/api/health/live")
    assert resp.status_code == 200
    assert resp.json() == {"status": "alive"}


# ---------------------------------------------------------------------------
# /api/health/ready
# ---------------------------------------------------------------------------


def test_health_ready_200_when_critical_ready() -> None:
    from searchat.api.readiness import get_readiness

    r = get_readiness()
    for comp in ("duckdb", "parquet", "search_engine", "metadata"):
        r.set_component(comp, "ready")

    mod = _api_app_module()
    client = TestClient(mod.app, raise_server_exceptions=False)
    resp = client.get("/api/health/ready")
    assert resp.status_code == 200
    body = resp.json()
    assert body["ready"] is True
    assert body["errors"] == {}


def test_health_ready_503_when_component_error() -> None:
    from searchat.api.readiness import get_readiness

    r = get_readiness()
    for comp in ("duckdb", "parquet", "search_engine", "metadata"):
        r.set_component(comp, "ready")
    r.set_component("duckdb", "error", error="connection lost")

    mod = _api_app_module()
    client = TestClient(mod.app, raise_server_exceptions=False)
    resp = client.get("/api/health/ready")
    assert resp.status_code == 503
    body = resp.json()
    assert body["ready"] is False
    assert "duckdb" in body["errors"]


# ---------------------------------------------------------------------------
# /api/health (deep)
# ---------------------------------------------------------------------------


def test_health_deep_healthy_all_pass(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    import searchat.api.dependencies as deps

    data_dir = tmp_path / "data"
    data_dir.mkdir()
    (data_dir / "conversations.parquet").touch()

    backup_dir = tmp_path / "backups"
    backup_dir.mkdir()

    store = MagicMock()
    store.validate_parquet_scan.return_value = None
    store.count_conversations.return_value = 42

    faiss_index = MagicMock()
    faiss_index.ntotal = 100
    engine = MagicMock()
    engine.faiss_index = faiss_index
    engine.embedder = MagicMock()

    backup_manager = MagicMock()
    backup_manager.backup_dir = backup_dir

    monkeypatch.setattr(deps, "_duckdb_store", store)
    monkeypatch.setattr(deps, "_search_dir", tmp_path)
    monkeypatch.setattr(deps, "_search_engine", engine)
    monkeypatch.setattr(deps, "_backup_manager", backup_manager)
    monkeypatch.setattr(deps, "_config", MagicMock())

    mod = _api_app_module()
    client = TestClient(mod.app, raise_server_exceptions=False)
    resp = client.get("/api/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["healthy"] is True
    assert body["checks"]["duckdb"]["status"] == "ok"
    assert body["checks"]["duckdb"]["conversations"] == 42
    assert body["checks"]["faiss"]["status"] == "ok"
    assert body["checks"]["embedder"]["status"] == "ok"
    assert body["checks"]["data_directory"]["status"] == "ok"
    assert body["checks"]["backup_directory"]["status"] == "ok"
    assert body["checks"]["disk_space"]["status"] == "ok"


def test_health_deep_degraded_on_failure(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    import searchat.api.dependencies as deps

    data_dir = tmp_path / "data"
    data_dir.mkdir()
    (data_dir / "conversations.parquet").touch()

    backup_dir = tmp_path / "backups"
    backup_dir.mkdir()

    store = MagicMock()
    store.validate_parquet_scan.side_effect = RuntimeError("corrupt parquet")

    backup_manager = MagicMock()
    backup_manager.backup_dir = backup_dir

    monkeypatch.setattr(deps, "_duckdb_store", store)
    monkeypatch.setattr(deps, "_search_dir", tmp_path)
    monkeypatch.setattr(deps, "_search_engine", None)
    monkeypatch.setattr(deps, "_backup_manager", backup_manager)
    monkeypatch.setattr(deps, "_config", MagicMock())

    mod = _api_app_module()
    client = TestClient(mod.app, raise_server_exceptions=False)
    resp = client.get("/api/health")
    assert resp.status_code == 503
    body = resp.json()
    assert body["healthy"] is False
    assert body["checks"]["duckdb"]["status"] == "error"


def test_health_deep_faiss_not_loaded_when_engine_none(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    import searchat.api.dependencies as deps

    data_dir = tmp_path / "data"
    data_dir.mkdir()
    (data_dir / "conversations.parquet").touch()

    backup_dir = tmp_path / "backups"
    backup_dir.mkdir()

    store = MagicMock()
    store.validate_parquet_scan.return_value = None
    store.count_conversations.return_value = 10

    backup_manager = MagicMock()
    backup_manager.backup_dir = backup_dir

    monkeypatch.setattr(deps, "_duckdb_store", store)
    monkeypatch.setattr(deps, "_search_dir", tmp_path)
    monkeypatch.setattr(deps, "_search_engine", None)
    monkeypatch.setattr(deps, "_backup_manager", backup_manager)
    monkeypatch.setattr(deps, "_config", MagicMock())

    mod = _api_app_module()
    client = TestClient(mod.app, raise_server_exceptions=False)
    resp = client.get("/api/health")
    body = resp.json()
    assert body["checks"]["faiss"]["status"] == "error"
    assert body["checks"]["embedder"]["status"] == "error"


def test_health_deep_includes_latency_timings(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    import searchat.api.dependencies as deps

    data_dir = tmp_path / "data"
    data_dir.mkdir()
    (data_dir / "conversations.parquet").touch()

    backup_dir = tmp_path / "backups"
    backup_dir.mkdir()

    store = MagicMock()
    store.validate_parquet_scan.return_value = None
    store.count_conversations.return_value = 5

    faiss_index = MagicMock()
    faiss_index.ntotal = 50
    engine = MagicMock()
    engine.faiss_index = faiss_index
    engine.embedder = MagicMock()

    backup_manager = MagicMock()
    backup_manager.backup_dir = backup_dir

    monkeypatch.setattr(deps, "_duckdb_store", store)
    monkeypatch.setattr(deps, "_search_dir", tmp_path)
    monkeypatch.setattr(deps, "_search_engine", engine)
    monkeypatch.setattr(deps, "_backup_manager", backup_manager)
    monkeypatch.setattr(deps, "_config", MagicMock())

    mod = _api_app_module()
    client = TestClient(mod.app, raise_server_exceptions=False)
    resp = client.get("/api/health")
    body = resp.json()
    for check_name, check_data in body["checks"].items():
        assert "latency_ms" in check_data, f"{check_name} missing latency_ms"
        assert isinstance(check_data["latency_ms"], (int, float))


def test_health_deep_disk_space_warning(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    import searchat.api.dependencies as deps

    data_dir = tmp_path / "data"
    data_dir.mkdir()
    (data_dir / "conversations.parquet").touch()

    backup_dir = tmp_path / "backups"
    backup_dir.mkdir()

    store = MagicMock()
    store.validate_parquet_scan.return_value = None
    store.count_conversations.return_value = 1

    faiss_index = MagicMock()
    faiss_index.ntotal = 10
    engine = MagicMock()
    engine.faiss_index = faiss_index
    engine.embedder = MagicMock()

    backup_manager = MagicMock()
    backup_manager.backup_dir = backup_dir

    monkeypatch.setattr(deps, "_duckdb_store", store)
    monkeypatch.setattr(deps, "_search_dir", tmp_path)
    monkeypatch.setattr(deps, "_search_engine", engine)
    monkeypatch.setattr(deps, "_backup_manager", backup_manager)
    monkeypatch.setattr(deps, "_config", MagicMock())

    # Simulate low disk space: 500MB free
    low_usage = MagicMock()
    low_usage.free = 500 * 1024**2
    monkeypatch.setattr(shutil, "disk_usage", lambda _path: low_usage)

    mod = _api_app_module()
    client = TestClient(mod.app, raise_server_exceptions=False)
    resp = client.get("/api/health")
    body = resp.json()
    assert body["checks"]["disk_space"]["status"] == "warning"
    assert body["healthy"] is False
