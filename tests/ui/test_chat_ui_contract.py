from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from searchat.api.app import app


def test_chat_page_contains_chat_controls():
    """Chat controls live in the standalone /chat page (moved from index.html)."""
    client = TestClient(app)
    resp = client.get("/chat")
    assert resp.status_code == 200

    html = resp.text
    assert "id=\"chatTemperature\"" in html
    assert "id=\"chatMaxTokens\"" in html
    assert "id=\"chatSystemPrompt\"" in html
    assert "id=\"chatSources\"" in html


def test_chat_js_targets_rag_endpoint_and_persists_options():
    chat_js = (
        Path(__file__).resolve().parents[2]
        / "src"
        / "searchat"
        / "web"
        / "static"
        / "js"
        / "modules"
        / "chat.js"
    )

    content = chat_js.read_text(encoding="utf-8")
    assert "/api/chat-rag" in content
    assert "chatTemperature" in content
    assert "chatMaxTokens" in content
    assert "chatSystemPrompt" in content
    assert "localStorage.setItem('chatTemperature'" in content
    assert "localStorage.setItem('chatMaxTokens'" in content
    assert "localStorage.setItem('chatSystemPrompt'" in content
    assert "event.key === 'Enter'" in content


def test_alpine_chat_store_uses_rag_request_shape_and_session_tracking():
    chat_store = (
        Path(__file__).resolve().parents[2]
        / "src"
        / "searchat"
        / "web"
        / "static"
        / "js"
        / "src"
        / "stores"
        / "chat.ts"
    )

    content = chat_store.read_text(encoding="utf-8")
    assert 'fetch("/api/chat-rag"' in content
    assert 'model_provider: this.provider' in content
    assert "body.model_name = this.model" in content
    assert "body.session_id = this.sessionId" in content
    assert 'localStorage.getItem("chatSessionId")' in content
    assert 'localStorage.setItem("chatSessionId", this.sessionId)' in content
