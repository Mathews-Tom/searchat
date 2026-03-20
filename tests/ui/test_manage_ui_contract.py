from __future__ import annotations

from pathlib import Path

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


def test_manage_page_uses_api_bootstrap_for_list_and_preview_panels() -> None:
    client = TestClient(app)
    resp = client.get("/manage")
    assert resp.status_code == 200

    html = resp.text
    assert 'id="manage-list"' in html
    assert 'id="previewOverlay"' in html
    assert 'id="previewCloseButton"' in html
    assert 'id="manageSelectAllButton"' in html
    assert 'id="manageDeselectAllButton"' in html
    assert 'id="manageDeleteBtn"' in html
    assert 'hx-get="/fragments/manage-conversations"' not in html
    assert 'onclick="manageSelectAll()"' not in html
    assert 'onclick="manageDeselectAll()"' not in html
    assert 'onclick="manageDeleteSelected()"' not in html
    assert 'onclick="closePreviewPanel()"' not in html


def test_manage_module_owns_manage_page_loading_and_preview_contracts() -> None:
    module_path = (
        Path(__file__).resolve().parents[2]
        / "src"
        / "searchat"
        / "web"
        / "static"
        / "js"
        / "modules"
        / "manage.js"
    )

    content = module_path.read_text(encoding="utf-8")
    assert "export function initManagePage()" in content
    assert "fetch(`/api/conversations/all?" in content
    assert "fetch(`/api/conversation/${encodeURIComponent(conversationId)}`)" in content
    assert "/fragments/manage-conversations" not in content
    assert "/fragments/conversation-preview" not in content
