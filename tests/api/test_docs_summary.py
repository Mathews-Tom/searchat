from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import Mock, patch

import pytest
from fastapi.testclient import TestClient

from searchat.api.app import app
from searchat.models import SearchResult, SearchResults


@pytest.fixture
def client():
    return TestClient(app)


def _make_results() -> SearchResults:
    now = datetime.now(timezone.utc)
    r = SearchResult(
        conversation_id="conv-1",
        project_id="p",
        title="T",
        created_at=now,
        updated_at=now,
        message_count=3,
        file_path="/home/user/.claude/projects/p/conv.jsonl",
        score=0.9,
        snippet="snippet",
        message_start_index=0,
        message_end_index=1,
    )
    return SearchResults(results=[r], total_count=1, search_time_ms=1.0, mode_used="hybrid")


def test_docs_summary_disabled_returns_404(client):
    cfg = Mock()
    cfg.export = Mock(enable_tech_docs=False)

    with patch("searchat.api.routers.docs.deps.get_config", return_value=cfg):
        resp = client.post(
            "/api/docs/summary",
            json={"sections": [{"name": "S", "query": "q"}]},
        )

    assert resp.status_code == 404


def test_docs_summary_markdown_returns_content_and_citations(client):
    cfg = Mock()
    cfg.export = Mock(enable_tech_docs=True)

    engine = Mock()
    engine.search.return_value = _make_results()

    with patch("searchat.api.routers.docs.deps.get_config", return_value=cfg):
        with patch("searchat.api.routers.docs.deps.get_search_engine", return_value=engine):
            resp = client.post(
                "/api/docs/summary",
                json={
                    "title": "My Doc",
                    "format": "markdown",
                    "sections": [
                        {"name": "Section A", "query": "how do we index?", "max_results": 5}
                    ],
                },
            )

    assert resp.status_code == 200
    data = resp.json()
    assert data["title"] == "My Doc"
    assert data["format"] == "markdown"
    assert "# My Doc" in data["content"]
    assert data["citation_count"] == 1
    assert data["citations"][0]["conversation_id"] == "conv-1"


def test_docs_summary_asciidoc_returns_content(client):
    cfg = Mock()
    cfg.export = Mock(enable_tech_docs=True)

    engine = Mock()
    engine.search.return_value = _make_results()

    with patch("searchat.api.routers.docs.deps.get_config", return_value=cfg):
        with patch("searchat.api.routers.docs.deps.get_search_engine", return_value=engine):
            resp = client.post(
                "/api/docs/summary",
                json={
                    "format": "asciidoc",
                    "sections": [{"name": "Section A", "query": "q"}],
                },
            )

    assert resp.status_code == 200
    data = resp.json()
    assert data["format"] == "asciidoc"
    assert data["content"].startswith("= ")
