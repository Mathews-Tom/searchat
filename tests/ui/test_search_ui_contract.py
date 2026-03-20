from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from searchat.api.app import app


def test_index_page_routes_primary_search_controls_through_js_actions() -> None:
    client = TestClient(app)
    resp = client.get("/")
    assert resp.status_code == 200

    html = resp.text
    assert 'id="search"' in html
    assert 'data-action="search"' in html
    assert 'data-action="showAllConversations"' in html
    assert 'data-action="showSearchView"' in html
    assert 'hx-get="/fragments/search-results"' not in html
    assert 'hx-get="/fragments/search-results?show_all=true"' not in html


def test_template_search_surface_matches_js_search_contract() -> None:
    template_path = (
        Path(__file__).resolve().parents[2]
        / "src"
        / "searchat"
        / "web"
        / "templates"
        / "index.html"
    )
    content = template_path.read_text(encoding="utf-8")

    assert 'data-action="search"' in content
    assert 'data-action="showAllConversations"' in content
    assert 'data-action="showSearchView"' in content
    assert 'hx-get="/fragments/search-results"' not in content
