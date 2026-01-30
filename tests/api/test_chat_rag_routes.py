from __future__ import annotations

from datetime import datetime, timedelta
from types import SimpleNamespace
from unittest.mock import Mock, patch

import pytest
from fastapi.testclient import TestClient

from searchat.api.app import app
from searchat.models import SearchResult


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture(autouse=True)
def semantic_components_ready():
    readiness = Mock()
    readiness.snapshot.return_value = Mock(
        components={"metadata": "ready", "faiss": "ready", "embedder": "ready"}
    )
    with patch("searchat.api.routers.chat.get_readiness", return_value=readiness):
        yield


def test_chat_rag_returns_answer_and_sources(client):
    now = datetime.now()
    result = SearchResult(
        conversation_id="test-conv-123",
        project_id="test-project",
        title="Test Conversation",
        created_at=now - timedelta(days=3),
        updated_at=now - timedelta(days=1),
        message_count=10,
        file_path="/home/user/.claude/projects/test/project/conv.jsonl",
        score=0.95,
        snippet="Snippet text",
        message_start_index=2,
        message_end_index=6,
    )

    generation = SimpleNamespace(answer="Final answer", results=[result], context_used=1)

    mock_generate = Mock(return_value=generation)
    config = Mock()
    config.chat = Mock(enable_rag=True, enable_citations=True)
    with patch("searchat.api.routers.chat.get_config", return_value=config):
        with patch("searchat.api.routers.chat.generate_rag_response", mock_generate):
            resp = client.post(
                "/api/chat-rag",
                json={
                    "query": "what is this?",
                    "model_provider": "ollama",
                    "model_name": "llama3",
                    "temperature": 0.2,
                    "max_tokens": 128,
                    "system_prompt": "Be strict.",
                },
            )

    assert resp.status_code == 200
    data = resp.json()
    assert data["answer"] == "Final answer"
    assert data["context_used"] == 1

    sources = data["sources"]
    assert isinstance(sources, list)
    assert len(sources) == 1

    s0 = sources[0]
    assert s0["conversation_id"] == "test-conv-123"
    assert s0["project_id"] == "test-project"
    assert s0["message_start_index"] == 2
    assert s0["message_end_index"] == 6
    assert "tool" in s0
    assert "source" in s0

    mock_generate.assert_called_once()
    _, kwargs = mock_generate.call_args
    assert kwargs["temperature"] == 0.2
    assert kwargs["max_tokens"] == 128
    assert kwargs["system_prompt"] == "Be strict."


def test_chat_rag_rejects_invalid_provider(client):
    resp = client.post("/api/chat-rag", json={"query": "x", "model_provider": "bad"})
    assert resp.status_code == 400


def test_chat_rag_temperature_validation(client):
    resp = client.post(
        "/api/chat-rag",
        json={"query": "x", "model_provider": "ollama", "temperature": 9.9},
    )
    assert resp.status_code == 422


def test_chat_rag_disabled_returns_404(client):
    config = Mock()
    config.chat = Mock(enable_rag=False, enable_citations=True)

    with patch("searchat.api.routers.chat.get_config", return_value=config):
        resp = client.post("/api/chat-rag", json={"query": "x", "model_provider": "ollama"})
    assert resp.status_code == 404


def test_chat_rag_citations_disabled_returns_no_sources(client):
    generation = SimpleNamespace(answer="Final", results=[], context_used=0)
    config = Mock()
    config.chat = Mock(enable_rag=True, enable_citations=False)

    with patch("searchat.api.routers.chat.get_config", return_value=config):
        with patch("searchat.api.routers.chat.generate_rag_response", return_value=generation):
            resp = client.post("/api/chat-rag", json={"query": "x", "model_provider": "ollama"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["sources"] == []
