from __future__ import annotations

import asyncio
import importlib
import os
import sys
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient


def _reset_readiness() -> None:
    from searchat.api.readiness import get_readiness

    r = get_readiness()
    snap = r.snapshot()
    for name in snap.components:
        r.set_component(name, "idle")
    r.set_watcher("disabled")


def _api_app_module():
    """Import the searchat.api.app *module*.

    NOTE: searchat.api exports a symbol named `app`, which shadows the submodule
    name `searchat.api.app` in regular import statements.
    """

    return importlib.import_module("searchat.api.app")


@pytest.fixture(autouse=True)
def _reset_dependencies_singletons(monkeypatch: pytest.MonkeyPatch) -> None:
    """Keep api dependency singletons isolated across tests."""
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
    deps._warmup_task = None
    deps.projects_cache = None
    deps.stats_cache = None
    deps.watcher_stats["indexed_count"] = 0
    deps.watcher_stats["last_update"] = None
    deps.indexing_state.update(
        {
            "in_progress": False,
            "operation": None,
            "started_at": None,
            "files_total": 0,
            "files_processed": 0,
        }
    )
    _reset_readiness()


def test_readiness_set_watcher_error_tracks_and_clears() -> None:
    from searchat.api.readiness import get_readiness

    r = get_readiness()
    r.set_watcher("error", error="boom")
    snap = r.snapshot()
    assert snap.watcher == "error"
    assert snap.errors["watcher"] == "boom"

    r.set_watcher("running")
    snap2 = r.snapshot()
    assert snap2.watcher == "running"
    assert "watcher" not in snap2.errors


@pytest.mark.asyncio
async def test_status_endpoint_returns_readiness_snapshot() -> None:
    from searchat.api.routers.status import get_status
    from searchat.api.readiness import get_readiness

    get_readiness().set_component("services", "ready")
    payload = await get_status()

    assert payload["components"]["services"] == "ready"
    assert set(payload.keys()) == {"server_started_at", "warmup_started_at", "components", "watcher", "errors"}


def test_status_features_endpoint_returns_flags(monkeypatch: pytest.MonkeyPatch) -> None:
    from searchat.api.app import app

    config = SimpleNamespace(
        analytics=SimpleNamespace(enabled=True),
        chat=SimpleNamespace(enable_rag=True, enable_citations=False),
        export=SimpleNamespace(enable_ipynb=False, enable_pdf=True, enable_tech_docs=False),
        dashboards=SimpleNamespace(enabled=True),
        snapshots=SimpleNamespace(enabled=True),
    )
    monkeypatch.setattr("searchat.api.routers.status.deps.get_config", lambda: config)

    client = TestClient(app)
    resp = client.get("/api/status/features")
    assert resp.status_code == 200
    data = resp.json()
    assert data["analytics"]["enabled"] is True
    assert data["chat"]["enable_rag"] is True
    assert data["chat"]["enable_citations"] is False
    assert data["export"]["enable_pdf"] is True
    assert data["snapshots"]["enabled"] is True


def test_dependencies_getters_raise_when_not_initialized() -> None:
    import searchat.api.dependencies as deps

    with pytest.raises(RuntimeError):
        deps.get_config()
    with pytest.raises(RuntimeError):
        deps.get_search_dir()
    with pytest.raises(RuntimeError):
        deps.get_duckdb_store()
    with pytest.raises(RuntimeError):
        deps.get_search_engine()
    with pytest.raises(RuntimeError):
        deps.get_backup_manager()
    with pytest.raises(RuntimeError):
        deps.get_platform_manager()


def test_start_background_warmup_no_event_loop_returns(monkeypatch: pytest.MonkeyPatch) -> None:
    import searchat.api.dependencies as deps

    deps._config = object()
    deps._search_dir = object()

    # Called from sync context: no running event loop.
    deps.start_background_warmup()


def test_initialize_services_sets_error_on_exception(monkeypatch: pytest.MonkeyPatch) -> None:
    import searchat.api.dependencies as deps
    from searchat.api.readiness import get_readiness

    def boom():
        raise RuntimeError("no config")

    monkeypatch.setattr(deps, "Config", SimpleNamespace(load=boom))

    with pytest.raises(RuntimeError):
        deps.initialize_services()

    snap = get_readiness().snapshot()
    assert snap.components["services"] == "error"
    assert "services" in snap.errors


def test_dependencies_indexer_is_created_lazily(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    import searchat.api.dependencies as deps

    deps._config = object()
    deps._search_dir = tmp_path

    fake_indexer = object()

    class FakeIndexer:
        def __new__(cls, *args, **kwargs):
            return fake_indexer

    monkeypatch.setattr("searchat.core.indexer.ConversationIndexer", FakeIndexer)

    idx = deps.get_indexer()
    assert idx is fake_indexer


@pytest.mark.asyncio
async def test_app_shutdown_stops_watcher(monkeypatch: pytest.MonkeyPatch) -> None:
    api_app = _api_app_module()

    watcher = MagicMock()
    set_watcher_mock = MagicMock()
    monkeypatch.setattr(api_app, "get_watcher", lambda: watcher)
    monkeypatch.setattr(api_app, "set_watcher", set_watcher_mock)
    monkeypatch.setattr(api_app, "initialize_services", MagicMock())
    monkeypatch.setattr(api_app, "start_background_warmup", MagicMock())
    monkeypatch.setattr(api_app, "get_config", lambda: SimpleNamespace(logging=SimpleNamespace()))
    monkeypatch.setattr(api_app, "setup_logging", MagicMock())
    monkeypatch.setattr(api_app.asyncio, "create_task", lambda coro: (coro.close(), MagicMock())[1])

    async with api_app.lifespan(MagicMock()):
        pass  # shutdown runs after yield

    watcher.stop.assert_called_once()
    set_watcher_mock.assert_called_with(None)


@pytest.mark.asyncio
async def test_app_lifespan_initializes_services_and_schedules_watcher(monkeypatch: pytest.MonkeyPatch) -> None:
    api_app = _api_app_module()

    monkeypatch.setattr(api_app, "initialize_services", MagicMock())
    monkeypatch.setattr(api_app, "start_background_warmup", MagicMock())
    monkeypatch.setattr(api_app, "get_config", lambda: SimpleNamespace(logging=SimpleNamespace()))
    monkeypatch.setattr(api_app, "setup_logging", MagicMock())
    monkeypatch.setattr(api_app, "get_watcher", lambda: None)

    scheduled = {"called": False}

    def _fake_create_task(coro):
        scheduled["called"] = True
        coro.close()
        return MagicMock()

    monkeypatch.setattr(api_app.asyncio, "create_task", _fake_create_task)

    async with api_app.lifespan(MagicMock()):
        assert scheduled["called"] is True


@pytest.mark.asyncio
async def test_app_lifespan_profile_logging(monkeypatch: pytest.MonkeyPatch) -> None:
    api_app = _api_app_module()

    monkeypatch.setenv("SEARCHAT_PROFILE_STARTUP", "1")
    monkeypatch.setattr(api_app, "initialize_services", MagicMock())
    monkeypatch.setattr(api_app, "start_background_warmup", MagicMock())
    monkeypatch.setattr(api_app, "get_config", lambda: SimpleNamespace(logging=SimpleNamespace()))
    monkeypatch.setattr(api_app, "setup_logging", MagicMock())
    monkeypatch.setattr(api_app, "get_watcher", lambda: None)

    logger = MagicMock()
    monkeypatch.setattr(api_app, "get_logger", lambda *_args, **_kwargs: logger)

    def _fake_create_task(coro):
        coro.close()
        return MagicMock()

    monkeypatch.setattr(api_app.asyncio, "create_task", _fake_create_task)

    async with api_app.lifespan(MagicMock()):
        assert logger.info.call_count >= 2


@pytest.mark.asyncio
async def test_app_root_and_conversation_page_serve_cached_html() -> None:
    api_app = _api_app_module()

    root_resp = await api_app.root()
    conv_resp = await api_app.serve_conversation_page("conv-1")
    assert root_resp.body == conv_resp.body


@pytest.mark.asyncio
async def test_favicon_ico_redirects_to_svg() -> None:
    api_app = _api_app_module()

    resp = await api_app.favicon_ico()
    assert resp.status_code in {302, 307, 308}
    assert resp.headers.get("location") == "/static/favicon.svg"


def test_on_new_conversations_indexes_and_invalidates(monkeypatch: pytest.MonkeyPatch) -> None:
    api_app = _api_app_module()
    import searchat.api.dependencies as deps

    fake_stats = SimpleNamespace(new_conversations=2, update_time_seconds=0.01)
    indexer = SimpleNamespace(index_append_only=MagicMock(return_value=fake_stats))

    monkeypatch.setattr(api_app, "get_indexer", lambda: indexer)
    monkeypatch.setattr(api_app, "get_search_engine", lambda: object())
    invalidate = MagicMock()
    monkeypatch.setattr(deps, "invalidate_search_index", invalidate)

    api_app.on_new_conversations(["a.jsonl", "b.jsonl"])

    assert api_app.indexing_state["in_progress"] is False
    invalidate.assert_called_once()


def test_on_new_conversations_uses_adaptive_when_enabled(monkeypatch: pytest.MonkeyPatch) -> None:
    api_app = _api_app_module()
    import searchat.api.dependencies as deps

    fake_stats = SimpleNamespace(new_conversations=0, updated_conversations=1, update_time_seconds=0.01)

    class FakeIndexing:
        enable_adaptive_indexing = True

    class FakeConfig:
        indexing = FakeIndexing()

    indexer = SimpleNamespace(
        config=FakeConfig(),
        index_adaptive=MagicMock(return_value=fake_stats),
        index_append_only=MagicMock(),
    )

    monkeypatch.setattr(api_app, "get_indexer", lambda: indexer)
    monkeypatch.setattr(api_app, "get_search_engine", lambda: object())
    invalidate = MagicMock()
    monkeypatch.setattr(deps, "invalidate_search_index", invalidate)

    api_app.on_new_conversations(["a.jsonl"])

    indexer.index_adaptive.assert_called_once()
    indexer.index_append_only.assert_not_called()
    invalidate.assert_called_once()


def test_on_new_conversations_handles_config_error(monkeypatch: pytest.MonkeyPatch) -> None:
    api_app = _api_app_module()
    import searchat.api.dependencies as deps

    fake_stats = SimpleNamespace(new_conversations=1, update_time_seconds=0.01)

    class BadIndexer:
        def __init__(self):
            self.index_append_only = MagicMock(return_value=fake_stats)

        @property
        def config(self):
            raise RuntimeError("boom")

    indexer = BadIndexer()

    monkeypatch.setattr(api_app, "get_indexer", lambda: indexer)
    monkeypatch.setattr(api_app, "get_search_engine", lambda: object())
    invalidate = MagicMock()
    monkeypatch.setattr(deps, "invalidate_search_index", invalidate)

    api_app.on_new_conversations(["a.jsonl"])

    indexer.index_append_only.assert_called_once()
    invalidate.assert_called_once()


def test_on_new_conversations_handles_indexer_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    api_app = _api_app_module()

    monkeypatch.setattr(api_app, "get_indexer", lambda: (_ for _ in ()).throw(RuntimeError("boom")))
    monkeypatch.setattr(api_app, "get_search_engine", lambda: object())

    api_app.on_new_conversations(["a.jsonl"])
    assert api_app.indexing_state["in_progress"] is False


@pytest.mark.asyncio
async def test_start_watcher_background_sets_readiness_running(monkeypatch: pytest.MonkeyPatch) -> None:
    api_app = _api_app_module()
    from searchat.api.readiness import get_readiness

    class FakeWatcher:
        def __init__(self, **kwargs):
            self._indexed = None

        def set_indexed_files(self, paths):
            self._indexed = paths

        def start(self):
            return None

        def get_watched_directories(self):
            return ["/tmp"]

    indexer = SimpleNamespace(get_indexed_file_paths=lambda: ["x.jsonl"])
    monkeypatch.setattr(api_app, "get_indexer", lambda: indexer)
    monkeypatch.setattr(api_app, "ConversationWatcher", FakeWatcher)
    monkeypatch.setattr(api_app, "set_watcher", MagicMock())

    await api_app._start_watcher_background(SimpleNamespace())
    assert get_readiness().snapshot().watcher == "running"


@pytest.mark.asyncio
async def test_start_watcher_background_sets_readiness_error_on_exception(monkeypatch: pytest.MonkeyPatch) -> None:
    api_app = _api_app_module()
    from searchat.api.readiness import get_readiness

    class BoomWatcher:
        def __init__(self, **kwargs):
            raise RuntimeError("no watcher")

    monkeypatch.setattr(api_app, "get_indexer", lambda: object())
    monkeypatch.setattr(api_app, "ConversationWatcher", BoomWatcher)

    await api_app._start_watcher_background(SimpleNamespace())
    snap = get_readiness().snapshot()
    assert snap.watcher == "error"
    assert "watcher" in snap.errors


def test_app_main_invalid_port_prints_and_returns(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    api_app = _api_app_module()

    monkeypatch.setenv(api_app.ENV_PORT, "not-a-number")
    api_app.main()
    out = capsys.readouterr().out
    assert "Invalid" in out or "invalid" in out


def test_app_main_invalid_port_out_of_range(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    api_app = _api_app_module()

    monkeypatch.setenv(api_app.ENV_PORT, "70000")
    api_app.main()
    out = capsys.readouterr().out
    assert "Invalid" in out or "invalid" in out


def test_app_main_scans_for_available_port_and_calls_uvicorn(monkeypatch: pytest.MonkeyPatch) -> None:
    api_app = _api_app_module()

    monkeypatch.delenv(api_app.ENV_PORT, raising=False)
    monkeypatch.setenv(api_app.ENV_HOST, "127.0.0.1")

    # Keep scan to a single port.
    monkeypatch.setattr(api_app, "PORT_SCAN_RANGE", (54321, 54321))

    class DummySocket:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def bind(self, addr):
            return None

    import types

    fake_socket_mod = types.SimpleNamespace(AF_INET=0, SOCK_STREAM=0, socket=lambda *a, **k: DummySocket())
    fake_uvicorn = types.SimpleNamespace(run=MagicMock())

    monkeypatch.setitem(os.environ, api_app.ENV_HOST, "127.0.0.1")
    monkeypatch.setitem(os.environ, api_app.ENV_PORT, "")

    monkeypatch.setitem(sys.modules, "socket", fake_socket_mod)
    monkeypatch.setitem(sys.modules, "uvicorn", fake_uvicorn)

    api_app.main()
    fake_uvicorn.run.assert_called_once()


def test_app_main_port_scan_exhausted(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    api_app = _api_app_module()

    monkeypatch.delenv(api_app.ENV_PORT, raising=False)
    monkeypatch.setenv(api_app.ENV_HOST, "127.0.0.1")
    monkeypatch.setattr(api_app, "PORT_SCAN_RANGE", (54321, 54321))

    class FailingSocket:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def bind(self, addr):
            raise OSError("port in use")

    import types

    fake_socket_mod = types.SimpleNamespace(AF_INET=0, SOCK_STREAM=0, socket=lambda *a, **k: FailingSocket())
    fake_uvicorn = types.SimpleNamespace(run=MagicMock())

    monkeypatch.setitem(sys.modules, "socket", fake_socket_mod)
    monkeypatch.setitem(sys.modules, "uvicorn", fake_uvicorn)

    api_app.main()
    out = capsys.readouterr().out
    assert "ports" in out or "ports" in out.lower()
    fake_uvicorn.run.assert_not_called()


def test_chat_rejects_invalid_provider() -> None:
    from searchat.api.app import app

    client = TestClient(app)
    response = client.post(
        "/api/chat",
        json={"query": "hi", "model_provider": "invalid"},
    )

    assert response.status_code == 400
    assert "model_provider" in response.json()["detail"]


def test_chat_returns_warming_until_ready(monkeypatch: pytest.MonkeyPatch) -> None:
    from searchat.api.app import app
    from searchat.api.readiness import get_readiness

    readiness = get_readiness()
    readiness.set_component("metadata", "loading")
    readiness.set_component("faiss", "idle")
    readiness.set_component("embedder", "idle")

    warmup = MagicMock()
    monkeypatch.setattr("searchat.api.routers.chat.trigger_search_engine_warmup", warmup)

    client = TestClient(app)
    response = client.post(
        "/api/chat",
        json={"query": "hello", "model_provider": "openai"},
    )

    assert response.status_code == 503
    warmup.assert_called_once()


def test_chat_returns_error_payload_on_component_error() -> None:
    from searchat.api.app import app
    from searchat.api.readiness import get_readiness

    readiness = get_readiness()
    readiness.set_component("metadata", "error", error="boom")
    readiness.set_component("faiss", "ready")
    readiness.set_component("embedder", "ready")

    client = TestClient(app)
    response = client.post(
        "/api/chat",
        json={"query": "hello", "model_provider": "openai"},
    )

    assert response.status_code == 500
    assert response.json()["status"] == "error"


def test_chat_streams_response_when_ready(monkeypatch: pytest.MonkeyPatch) -> None:
    from searchat.api.app import app
    from searchat.api.readiness import get_readiness

    readiness = get_readiness()
    readiness.set_component("metadata", "ready")
    readiness.set_component("faiss", "ready")
    readiness.set_component("embedder", "ready")

    def _fake_stream():
        yield "hello"
        yield " world"

    monkeypatch.setattr("searchat.api.routers.chat.get_config", lambda: object())
    monkeypatch.setattr("searchat.api.routers.chat.generate_answer_stream", lambda **_kwargs: _fake_stream())

    client = TestClient(app)
    response = client.post(
        "/api/chat",
        json={"query": "hello", "model_provider": "ollama"},
    )

    assert response.status_code == 200
    assert response.text == "hello world"


def test_chat_snapshot_mode_returns_403() -> None:
    from searchat.api.app import app
    from searchat.api.readiness import get_readiness

    readiness = get_readiness()
    readiness.set_component("metadata", "ready")
    readiness.set_component("faiss", "ready")
    readiness.set_component("embedder", "ready")

    client = TestClient(app)
    response = client.post(
        "/api/chat?snapshot=backup_20250101_000000",
        json={"query": "hello", "model_provider": "openai"},
    )
    assert response.status_code == 403
    assert response.json()["detail"] == "Chat is disabled in snapshot mode"


def test_chat_returns_400_on_generate_value_error(monkeypatch: pytest.MonkeyPatch) -> None:
    from searchat.api.app import app
    from searchat.api.readiness import get_readiness

    readiness = get_readiness()
    readiness.set_component("metadata", "ready")
    readiness.set_component("faiss", "ready")
    readiness.set_component("embedder", "ready")

    monkeypatch.setattr("searchat.api.routers.chat.get_config", lambda: object())
    monkeypatch.setattr(
        "searchat.api.routers.chat.generate_answer_stream",
        lambda **_kwargs: (_ for _ in ()).throw(ValueError("bad")),
    )

    client = TestClient(app)
    resp = client.post("/api/chat", json={"query": "hello", "model_provider": "openai"})
    assert resp.status_code == 400
    assert resp.json()["detail"] == "bad"


def test_chat_returns_503_on_generate_llm_error(monkeypatch: pytest.MonkeyPatch) -> None:
    from searchat.api.app import app
    from searchat.api.readiness import get_readiness
    from searchat.services.llm_service import LLMServiceError

    readiness = get_readiness()
    readiness.set_component("metadata", "ready")
    readiness.set_component("faiss", "ready")
    readiness.set_component("embedder", "ready")

    monkeypatch.setattr("searchat.api.routers.chat.get_config", lambda: object())
    monkeypatch.setattr(
        "searchat.api.routers.chat.generate_answer_stream",
        lambda **_kwargs: (_ for _ in ()).throw(LLMServiceError("nope")),
    )

    client = TestClient(app)
    resp = client.post("/api/chat", json={"query": "hello", "model_provider": "openai"})
    assert resp.status_code == 503
    assert resp.json()["detail"] == "nope"


def test_chat_returns_500_on_generate_unexpected_error(monkeypatch: pytest.MonkeyPatch) -> None:
    from searchat.api.app import app
    from searchat.api.readiness import get_readiness

    readiness = get_readiness()
    readiness.set_component("metadata", "ready")
    readiness.set_component("faiss", "ready")
    readiness.set_component("embedder", "ready")

    monkeypatch.setattr("searchat.api.routers.chat.get_config", lambda: object())
    monkeypatch.setattr(
        "searchat.api.routers.chat.generate_answer_stream",
        lambda **_kwargs: (_ for _ in ()).throw(RuntimeError("boom")),
    )

    client = TestClient(app)
    resp = client.post("/api/chat", json={"query": "hello", "model_provider": "openai"})
    assert resp.status_code == 500
    assert resp.json()["detail"] == "boom"


def test_dependencies_is_valid_snapshot_name() -> None:
    import searchat.api.dependencies as deps

    assert deps._is_valid_snapshot_name("backup_20250101_000000") is True
    assert deps._is_valid_snapshot_name("") is False
    assert deps._is_valid_snapshot_name(".") is False
    assert deps._is_valid_snapshot_name("..") is False
    assert deps._is_valid_snapshot_name("a/b") is False
    assert deps._is_valid_snapshot_name("a\\b") is False
    assert deps._is_valid_snapshot_name("..x") is False


def test_resolve_dataset_search_dir_snapshot_mode_disabled(tmp_path) -> None:
    import searchat.api.dependencies as deps

    deps._search_dir = tmp_path
    deps._config = SimpleNamespace(snapshots=SimpleNamespace(enabled=False))
    deps._backup_manager = SimpleNamespace(backup_dir=tmp_path, validate_backup=lambda _p: True)

    try:
        deps.resolve_dataset_search_dir("backup_20250101_000000")
        raise AssertionError("expected ValueError")
    except ValueError as exc:
        assert str(exc) == "Snapshot mode is disabled"


def test_resolve_dataset_search_dir_invalid_name(tmp_path) -> None:
    import searchat.api.dependencies as deps

    deps._search_dir = tmp_path
    deps._config = SimpleNamespace(snapshots=SimpleNamespace(enabled=True))
    deps._backup_manager = SimpleNamespace(backup_dir=tmp_path, validate_backup=lambda _p: True)

    try:
        deps.resolve_dataset_search_dir("../nope")
        raise AssertionError("expected ValueError")
    except ValueError as exc:
        assert str(exc) == "Invalid snapshot name"


def test_resolve_dataset_search_dir_invalid_snapshot_path_symlink(tmp_path) -> None:
    import searchat.api.dependencies as deps

    backup_root = tmp_path / "backups"
    backup_root.mkdir()
    outside = tmp_path / "outside"
    outside.mkdir()
    (backup_root / "snap").symlink_to(outside, target_is_directory=True)

    deps._search_dir = tmp_path
    deps._config = SimpleNamespace(snapshots=SimpleNamespace(enabled=True))
    deps._backup_manager = SimpleNamespace(backup_dir=backup_root, validate_backup=lambda _p: True)

    try:
        deps.resolve_dataset_search_dir("snap")
        raise AssertionError("expected ValueError")
    except ValueError as exc:
        assert str(exc) == "Invalid snapshot path"


def test_resolve_dataset_search_dir_not_found(tmp_path) -> None:
    import searchat.api.dependencies as deps

    backup_root = tmp_path / "backups"
    backup_root.mkdir()

    deps._search_dir = tmp_path
    deps._config = SimpleNamespace(snapshots=SimpleNamespace(enabled=True))
    deps._backup_manager = SimpleNamespace(backup_dir=backup_root, validate_backup=lambda _p: True)

    try:
        deps.resolve_dataset_search_dir("missing")
        raise AssertionError("expected ValueError")
    except ValueError as exc:
        assert str(exc) == "Snapshot not found"


def test_resolve_dataset_search_dir_validation_failed(tmp_path) -> None:
    import searchat.api.dependencies as deps

    backup_root = tmp_path / "backups"
    backup_root.mkdir()
    (backup_root / "snap").mkdir()

    deps._search_dir = tmp_path
    deps._config = SimpleNamespace(snapshots=SimpleNamespace(enabled=True))
    deps._backup_manager = SimpleNamespace(backup_dir=backup_root, validate_backup=lambda _p: False)

    try:
        deps.resolve_dataset_search_dir("snap")
        raise AssertionError("expected ValueError")
    except ValueError as exc:
        assert str(exc) == "Snapshot validation failed"


def test_resolve_dataset_search_dir_returns_snapshot_dir(tmp_path) -> None:
    import searchat.api.dependencies as deps

    backup_root = tmp_path / "backups"
    backup_root.mkdir()
    snapshot_dir = backup_root / "snap"
    snapshot_dir.mkdir()

    deps._search_dir = tmp_path
    deps._config = SimpleNamespace(snapshots=SimpleNamespace(enabled=True))
    deps._backup_manager = SimpleNamespace(backup_dir=backup_root, validate_backup=lambda _p: True)

    resolved, name = deps.resolve_dataset_search_dir("snap")
    assert resolved == snapshot_dir
    assert name == "snap"


@pytest.mark.asyncio
async def test_start_background_warmup_schedules_once(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    import searchat.api.dependencies as deps

    deps._config = object()
    deps._search_dir = tmp_path
    deps._warmup_task = None

    started = {"count": 0}
    block = asyncio.Event()

    async def _fake_warmup_all() -> None:
        started["count"] += 1
        await block.wait()

    monkeypatch.setattr(deps, "_warmup_all", _fake_warmup_all)

    deps.start_background_warmup()
    await asyncio.sleep(0)
    assert deps._warmup_task is not None
    task1: asyncio.Task[None] = deps._warmup_task  # type: ignore[assignment]
    assert task1.done() is False

    deps.start_background_warmup()
    assert deps._warmup_task is task1

    assert started["count"] == 1
    task1.cancel()
    try:
        await task1  # type: ignore[misc]
    except asyncio.CancelledError:
        pass


def test_warmup_duckdb_parquet_sets_error(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    import searchat.api.dependencies as deps
    from searchat.api.readiness import get_readiness

    class BoomStore:
        def validate_parquet_scan(self):
            raise RuntimeError("boom")

    deps._duckdb_store = BoomStore()
    deps._config = object()
    deps._search_dir = tmp_path

    deps._warmup_duckdb_parquet()
    snap = get_readiness().snapshot()
    assert snap.components["duckdb"] == "error"
    assert snap.components["parquet"] == "error"


def test_warmup_semantic_components_sets_error_only_for_not_ready(monkeypatch: pytest.MonkeyPatch) -> None:
    import searchat.api.dependencies as deps
    from searchat.api.readiness import get_readiness

    class FakeEngine:
        def ensure_metadata_ready(self):
            raise RuntimeError("boom")

        def ensure_faiss_loaded(self):
            raise AssertionError("should not be called")

        def ensure_embedder_loaded(self):
            raise AssertionError("should not be called")

    monkeypatch.setattr(deps, "_ensure_search_engine", lambda: FakeEngine())

    readiness = get_readiness()
    readiness.set_component("metadata", "idle")
    readiness.set_component("faiss", "ready")
    readiness.set_component("embedder", "idle")

    deps._warmup_semantic_components()
    snap = readiness.snapshot()
    assert snap.components["metadata"] == "error"
    assert snap.components["faiss"] == "ready"
    assert snap.components["embedder"] == "error"


def test_get_duckdb_store_for_caches_per_dataset(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    import searchat.api.dependencies as deps
    import searchat.api.duckdb_store as store_mod

    base = tmp_path / "base"
    base.mkdir()
    other = tmp_path / "other"
    other.mkdir()

    deps._search_dir = base
    deps._duckdb_store = object()
    deps._config = SimpleNamespace(performance=SimpleNamespace(memory_limit_mb=123))

    created: list[object] = []

    class FakeStore:
        def __init__(self, search_dir, memory_limit_mb=None):
            created.append((search_dir, memory_limit_mb))

    monkeypatch.setattr(store_mod, "DuckDBStore", FakeStore)

    assert deps.get_duckdb_store_for(base) is deps._duckdb_store

    s1 = deps.get_duckdb_store_for(other)
    s2 = deps.get_duckdb_store_for(other)
    assert s1 is s2
    assert created == [(other, 123)]


def test_get_or_create_search_engine_for_caches_per_dataset(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    import searchat.api.dependencies as deps
    import searchat.core.search_engine as se_mod

    base = tmp_path / "base"
    base.mkdir()
    other = tmp_path / "other"
    other.mkdir()

    deps._search_dir = base
    deps._config = object()
    deps._search_engine = object()

    created: list[object] = []

    class FakeEngine:
        def __init__(self, search_dir, _config):
            created.append(search_dir)

    monkeypatch.setattr(se_mod, "SearchEngine", FakeEngine)

    assert deps.get_or_create_search_engine_for(base) is deps._search_engine

    e1 = deps.get_or_create_search_engine_for(other)
    e2 = deps.get_or_create_search_engine_for(other)
    assert e1 is e2
    assert created == [other]


def test_ensure_search_engine_sets_readiness_error_on_failure(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    import searchat.api.dependencies as deps
    from searchat.api.readiness import get_readiness
    import searchat.core.search_engine as se_mod

    deps._config = object()
    deps._search_dir = tmp_path
    deps._search_engine = None

    class BoomEngine:
        def __init__(self, *_a, **_k):
            raise RuntimeError("boom")

    monkeypatch.setattr(se_mod, "SearchEngine", BoomEngine)

    with pytest.raises(RuntimeError):
        deps.get_or_create_search_engine()

    assert get_readiness().snapshot().components["search_engine"] == "error"


def test_ensure_indexer_sets_readiness_error_on_failure(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    import searchat.api.dependencies as deps
    from searchat.api.readiness import get_readiness
    import searchat.core.indexer as indexer_mod

    deps._config = object()
    deps._search_dir = tmp_path
    deps._indexer = None

    class BoomIndexer:
        def __init__(self, *_a, **_k):
            raise RuntimeError("boom")

    monkeypatch.setattr(indexer_mod, "ConversationIndexer", BoomIndexer)

    with pytest.raises(RuntimeError):
        deps.get_indexer()

    assert get_readiness().snapshot().components["indexer"] == "error"
