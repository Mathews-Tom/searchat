from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from searchat.api.app import app


def test_conversation_page_boots_from_results_container_instead_of_fragment_view() -> None:
    client = TestClient(app)
    resp = client.get("/conversation/test-conversation-id")
    assert resp.status_code == 200

    html = resp.text
    assert 'id="conversationHeader"' in html
    assert 'id="results"' in html
    assert 'data-conversation-id="test-conversation-id"' in html
    assert 'Loading conversation...' in html
    assert 'hx-get="/fragments/conversation-view/' not in html
    assert 'hx-trigger="load"' not in html


def test_conversation_template_uses_api_bootstrap_contract() -> None:
    template_path = (
        Path(__file__).resolve().parents[2]
        / "src"
        / "searchat"
        / "web"
        / "templates"
        / "conversation.html"
    )
    content = template_path.read_text(encoding="utf-8")

    assert 'id="conversationHeader"' in content
    assert 'id="results"' in content
    assert 'data-conversation-id="{{ conversation_id }}"' in content
    assert 'hx-get="/fragments/conversation-view/' not in content
