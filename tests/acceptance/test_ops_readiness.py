"""Acceptance coverage for operational readiness behavior in Wave 3."""
from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import Mock, patch

from fastapi.testclient import TestClient

from searchat.api.app import app


def test_status_endpoint_is_best_effort_when_capability_inspection_fails() -> None:
    config = SimpleNamespace(
        analytics=SimpleNamespace(enabled=True),
        chat=SimpleNamespace(enable_rag=True, enable_citations=True),
        export=SimpleNamespace(enable_ipynb=False, enable_pdf=True, enable_tech_docs=False),
        dashboards=SimpleNamespace(enabled=True),
        snapshots=SimpleNamespace(enabled=True),
    )

    failing_service = Mock()
    failing_service.describe_capabilities.side_effect = RuntimeError("introspection failed")

    with patch("searchat.api.routers.status.deps.get_config", return_value=config):
        with patch("searchat.api.dependencies._search_engine", failing_service):
            client = TestClient(app)
            response = client.get("/api/status/features")

    assert response.status_code == 200
    payload = response.json()
    assert payload["retrieval"] is None


def test_chat_rag_returns_warming_payload_when_semantic_components_are_idle() -> None:
    readiness = Mock()
    readiness.snapshot.return_value = Mock(
        components={"metadata": "idle", "faiss": "ready", "embedder": "ready"},
        watcher="disabled",
        errors={},
        warmup_started_at=None,
    )
    config = SimpleNamespace(chat=SimpleNamespace(enable_rag=True, enable_citations=True))

    with patch("searchat.api.readiness.get_readiness", return_value=readiness):
        with patch("searchat.api.routers.chat.get_config", return_value=config):
            with patch("searchat.api.warmup.trigger_search_engine_warmup") as warmup:
                client = TestClient(app)
                response = client.post("/api/chat-rag", json={"query": "x", "model_provider": "ollama"})

    assert response.status_code == 503
    assert response.json()["status"] == "warming"
    warmup.assert_called_once()


def test_chat_rag_fails_closed_when_capability_introspection_breaks() -> None:
    readiness = Mock()
    readiness.snapshot.return_value = Mock(
        components={"metadata": "ready", "faiss": "ready", "embedder": "ready"},
        watcher="disabled",
        errors={},
        warmup_started_at=None,
    )
    config = SimpleNamespace(chat=SimpleNamespace(enable_rag=True, enable_citations=True))

    with patch("searchat.api.readiness.get_readiness", return_value=readiness):
        with patch("searchat.api.routers.chat.get_config", return_value=config):
            with patch(
                "searchat.api.routers.chat.get_search_engine",
                side_effect=RuntimeError("service registry unavailable"),
            ):
                client = TestClient(app)
                response = client.post("/api/chat-rag", json={"query": "x", "model_provider": "ollama"})

    assert response.status_code == 500
    payload = response.json()
    assert payload["status"] == "error"
    assert payload["errors"]["semantic"] == (
        "Retrieval capability inspection failed: service registry unavailable"
    )


def test_agent_config_fails_closed_when_semantic_capability_is_unavailable() -> None:
    readiness = Mock()
    readiness.snapshot.return_value = Mock(
        components={"metadata": "ready", "faiss": "ready", "embedder": "ready"},
        watcher="disabled",
        errors={},
        warmup_started_at=None,
    )
    retrieval_service = Mock()
    retrieval_service.describe_capabilities.return_value = SimpleNamespace(
        semantic_available=False,
        reranking_available=True,
        semantic_reason="Embedding model unavailable: all-MiniLM-L6-v2",
        reranking_reason=None,
    )

    with patch("searchat.api.readiness.get_readiness", return_value=readiness):
        with patch("searchat.api.routers.docs.deps.get_search_engine", return_value=retrieval_service):
            client = TestClient(app)
            response = client.post(
                "/api/export/agent-config",
                json={"format": "claude.md", "model_provider": "ollama"},
            )

    assert response.status_code == 500
    payload = response.json()
    assert payload["status"] == "error"
    assert payload["errors"]["semantic"] == "Embedding model unavailable: all-MiniLM-L6-v2"
