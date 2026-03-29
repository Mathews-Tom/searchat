import pytest
from pathlib import Path
from unittest.mock import Mock, patch

from searchat.api import state as api_state


@pytest.mark.unit
def test_readiness_state_transitions():
    from searchat.api.readiness import get_readiness, warming_payload, error_payload

    readiness = get_readiness()

    # Warmup start is single-shot
    readiness.mark_warmup_started()
    assert readiness.mark_warmup_started() is False

    readiness.set_component("faiss", "loading")
    readiness.set_component("faiss", "error", error="boom")

    warm = warming_payload(retry_after_ms=123)
    assert warm["status"] == "warming"
    assert warm["retry_after_ms"] == 123
    assert warm["components"]["faiss"] == "error"
    assert warm["errors"]["faiss"] == "boom"

    err = error_payload()
    assert err["status"] == "error"
    assert err["errors"]["faiss"] == "boom"


@pytest.mark.unit
def test_invalidate_search_index_marks_semantic_stale():
    import searchat.api.dependencies as deps
    import searchat.api.warmup as api_warmup

    engine = Mock()
    with patch.object(api_warmup, "start_background_warmup") as start_warmup:
        deps._search_engine = engine
        api_state.projects_cache = ["x"]
        api_state.stats_cache = {"y": 1}

        # Pretend semantic components were ready
        readiness = deps.get_readiness()
        readiness.set_component("faiss", "ready")
        readiness.set_component("metadata", "ready")
        readiness.set_component("embedder", "ready")

        deps.invalidate_search_index()

        assert api_state.projects_cache is None
        assert api_state.stats_cache is None
        engine.refresh_index.assert_called_once()
        start_warmup.assert_called_once()

        snap = readiness.snapshot()
        assert snap.components["faiss"] == "idle"
        assert snap.components["metadata"] == "idle"
        assert snap.components["embedder"] == "idle"


@pytest.mark.unit
def test_warmup_semantic_components_sets_readiness_ready(tmp_path: Path):
    import searchat.api.dependencies as deps
    import searchat.api.warmup as api_warmup

    # Ensure services look initialized for the warmup guard.
    deps._config = Mock()
    deps._search_dir = tmp_path

    engine = Mock()
    engine.ensure_metadata_ready = Mock()
    engine.ensure_faiss_loaded = Mock()
    engine.ensure_embedder_loaded = Mock()

    with patch.object(deps, "_ensure_search_engine", return_value=engine):
        readiness = deps.get_readiness()
        readiness.set_component("faiss", "idle")
        readiness.set_component("metadata", "idle")
        readiness.set_component("embedder", "idle")

        api_warmup._warmup_semantic_components()

        engine.ensure_metadata_ready.assert_called_once()
        engine.ensure_faiss_loaded.assert_called_once()
        engine.ensure_embedder_loaded.assert_called_once()
        snap = readiness.snapshot()
        assert snap.components["faiss"] == "ready"
        assert snap.components["metadata"] == "ready"
        assert snap.components["embedder"] == "ready"


