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
    assert set(payload.keys()) == {"warmup_started_at", "components", "watcher", "errors"}


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
    monkeypatch.setattr(api_app, "get_watcher", lambda: watcher)
    monkeypatch.setattr(api_app, "set_watcher", MagicMock())

    await api_app.shutdown_event()
    watcher.stop.assert_called_once()


@pytest.mark.asyncio
async def test_app_startup_event_initializes_services_and_schedules_watcher(monkeypatch: pytest.MonkeyPatch) -> None:
    api_app = _api_app_module()

    monkeypatch.setattr(api_app, "initialize_services", MagicMock())
    monkeypatch.setattr(api_app, "start_background_warmup", MagicMock())
    monkeypatch.setattr(api_app, "get_config", lambda: SimpleNamespace(logging=SimpleNamespace()))
    monkeypatch.setattr(api_app, "setup_logging", MagicMock())

    scheduled = {"called": False}

    def _fake_create_task(coro):
        scheduled["called"] = True
        coro.close()
        return MagicMock()

    monkeypatch.setattr(api_app.asyncio, "create_task", _fake_create_task)
    await api_app.startup_event()

    assert scheduled["called"] is True


@pytest.mark.asyncio
async def test_app_startup_event_profile_logging(monkeypatch: pytest.MonkeyPatch) -> None:
    api_app = _api_app_module()

    monkeypatch.setenv("SEARCHAT_PROFILE_STARTUP", "1")
    monkeypatch.setattr(api_app, "initialize_services", MagicMock())
    monkeypatch.setattr(api_app, "start_background_warmup", MagicMock())
    monkeypatch.setattr(api_app, "get_config", lambda: SimpleNamespace(logging=SimpleNamespace()))
    monkeypatch.setattr(api_app, "setup_logging", MagicMock())

    logger = MagicMock()
    monkeypatch.setattr(api_app, "get_logger", lambda *_args, **_kwargs: logger)

    def _fake_create_task(coro):
        coro.close()
        return MagicMock()

    monkeypatch.setattr(api_app.asyncio, "create_task", _fake_create_task)

    await api_app.startup_event()

    assert logger.info.call_count >= 2


@pytest.mark.asyncio
async def test_app_root_and_conversation_page_serve_cached_html() -> None:
    api_app = _api_app_module()

    root_resp = await api_app.root()
    conv_resp = await api_app.serve_conversation_page("conv-1")
    assert root_resp.body == conv_resp.body


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
