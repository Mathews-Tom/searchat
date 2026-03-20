from __future__ import annotations

from fastapi.testclient import TestClient

from searchat.api.app import app


def test_manage_page_uses_select_backed_filters_instead_of_project_fragment() -> None:
    client = TestClient(app)
    resp = client.get("/manage")
    assert resp.status_code == 200

    html = resp.text
    assert 'id="manageProject"' in html
    assert 'id="manageTool"' in html
    assert 'id="manageSortBy"' in html
    assert 'data-for="manageProject"' in html
    assert 'data-for="manageTool"' in html
    assert 'data-for="manageSortBy"' in html
    assert 'hx-get="/fragments/manage-project-dropdown"' not in html
    assert 'onclick="manageSetFilter' not in html


def test_manage_page_keeps_fragment_list_loading_for_now() -> None:
    client = TestClient(app)
    resp = client.get("/manage")
    assert resp.status_code == 200

    html = resp.text
    assert 'id="manage-list"' in html
    assert 'hx-get="/fragments/manage-conversations"' in html
    assert 'hx-trigger="load, manage-reload from:body"' in html
