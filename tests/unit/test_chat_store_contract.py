from __future__ import annotations

from pathlib import Path


def test_chat_store_uses_rag_request_shape_and_session_tracking() -> None:
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
    assert 'body.model_name = this.model' in content
    assert "body.session_id = this.sessionId" in content
    assert 'localStorage.getItem("chatSessionId")' in content
    assert 'localStorage.setItem("chatSessionId", this.sessionId)' in content
    assert 'localStorage.removeItem("chatSessionId")' in content
