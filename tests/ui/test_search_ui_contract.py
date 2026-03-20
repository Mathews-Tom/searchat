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


def test_index_page_uses_select_backed_filters_for_search_ui() -> None:
    client = TestClient(app)
    resp = client.get("/")
    assert resp.status_code == 200

    html = resp.text
    assert 'id="mode"' in html
    assert 'id="project"' in html
    assert 'id="tool"' in html
    assert 'id="date"' in html
    assert 'id="sortBy"' in html
    assert 'data-for="project"' in html
    assert 'data-for="mode"' in html
    assert 'hx-get="/fragments/project-dropdown"' not in html
    assert 'hx-trigger="projectChanged from:body"' not in html


def test_template_filter_surface_no_longer_uses_fragment_backed_project_controls() -> None:
    template_path = (
        Path(__file__).resolve().parents[2]
        / "src"
        / "searchat"
        / "web"
        / "templates"
        / "index.html"
    )
    content = template_path.read_text(encoding="utf-8")

    assert 'id="project"' in content
    assert 'id="mode"' in content
    assert 'data-for="project"' in content
    assert 'hx-get="/fragments/project-dropdown"' not in content
    assert 'hx-get="/fragments/project-summary"' not in content


def test_index_page_routes_secondary_views_and_actions_through_js_modules() -> None:
    client = TestClient(app)
    resp = client.get("/")
    assert resp.status_code == 200

    html = resp.text
    for action in [
        "showBookmarks",
        "showAnalytics",
        "showDashboards",
        "showExpertise",
        "showContradictions",
        "saveQueryInline",
        "indexMissing",
        "createBackup",
        "showBackups",
        "shutdownServer",
    ]:
        assert f'data-action="{action}"' in html

    assert 'hx-get="/fragments/bookmarks-list"' not in html
    assert 'hx-get="/fragments/analytics-dashboard"' not in html
    assert 'hx-get="/fragments/dashboards-view"' not in html
    assert 'hx-get="/fragments/expertise-view"' not in html
    assert 'hx-get="/fragments/contradictions-view"' not in html
    assert 'hx-post="/fragments/index-missing"' not in html
    assert 'hx-post="/fragments/backup-create"' not in html
    assert 'hx-get="/fragments/backup-list"' not in html
    assert 'hx-post="/fragments/shutdown"' not in html


def test_index_page_saved_queries_panel_uses_js_module_contract() -> None:
    client = TestClient(app)
    resp = client.get("/")
    assert resp.status_code == 200

    html = resp.text
    assert 'id="saveQueryButton"' in html
    assert 'id="saveQueryButtonInline"' in html
    assert 'data-action="saveQueryInline"' in html
    assert 'id="savedQueriesList"' in html
    assert 'id="savedQueriesForm"' in html
    assert 'hx-get="/fragments/saved-queries-list"' not in html
    assert 'hx-post="/fragments/saved-query"' not in html


def test_index_page_dataset_selector_uses_dataset_module_contract() -> None:
    client = TestClient(app)
    resp = client.get("/")
    assert resp.status_code == 200

    html = resp.text
    assert 'id="datasetSelect"' in html
    assert 'id="datasetBanner"' in html
    assert 'hx-get="/fragments/dataset-options"' not in html
    assert 'x-model="$store.dataset.snapshotName"' not in html


def test_splash_bootstrap_skips_blocking_overlay_when_critical_components_are_ready() -> None:
    script_path = (
        Path(__file__).resolve().parents[2]
        / "src"
        / "searchat"
        / "web"
        / "static"
        / "js"
        / "splash.js"
    )
    content = script_path.read_text(encoding="utf-8")

    assert "function areCriticalComponentsReady(status)" in content
    assert "const criticalReady = areCriticalComponentsReady(status);" in content
    assert "if (criticalReady) {" in content
    assert "markSplashDismissedForServer(_currentServerStartedAt);" in content
    assert "setWarmupUI(false);" in content
    assert "renderSplash(status);" in content


def test_legacy_web_bootstrap_uses_dedicated_action_registry() -> None:
    script_path = (
        Path(__file__).resolve().parents[2]
        / "src"
        / "searchat"
        / "web"
        / "static"
        / "js"
        / "main.js"
    )
    content = script_path.read_text(encoding="utf-8")

    assert "const actionRegistry = window.searchatActions || (window.searchatActions = {});" in content
    assert "actionRegistry.search = search;" in content
    assert "const handler = action ? actionRegistry[action] : null;" in content
    assert "typeof handler === 'function'" in content


def test_bundled_entrypoint_imports_legacy_web_bootstrap() -> None:
    script_path = (
        Path(__file__).resolve().parents[2]
        / "src"
        / "searchat"
        / "web"
        / "static"
        / "js"
        / "src"
        / "main.ts"
    )
    content = script_path.read_text(encoding="utf-8")

    assert 'void import("../main.js")' in content
    assert 'Legacy web bootstrap failed:' in content


def test_expertise_records_use_inline_detail_expansion_contract() -> None:
    script_path = (
        Path(__file__).resolve().parents[2]
        / "src"
        / "searchat"
        / "web"
        / "static"
        / "js"
        / "modules"
        / "expertise.js"
    )
    content = script_path.read_text(encoding="utf-8")

    assert "function _openInlineRecordDetail(container, item)" in content
    assert "item.insertAdjacentElement('afterend', detailRow);" in content
    assert "container.querySelector('.expertise-inline-detail')?.remove();" in content
    assert "const detailAreaId = 'expertiseDetailArea';" not in content
    assert "detailArea.scrollIntoView" not in content


def test_contradictions_use_inline_detail_expansion_contract() -> None:
    script_path = (
        Path(__file__).resolve().parents[2]
        / "src"
        / "searchat"
        / "web"
        / "static"
        / "js"
        / "modules"
        / "contradictions.js"
    )
    content = script_path.read_text(encoding="utf-8")

    assert "function _openInlineContradictionDetail(container, item)" in content
    assert "item.insertAdjacentElement('afterend', detailRow);" in content
    assert "container.querySelector('.contradiction-inline-detail')?.remove();" in content
    assert '<div id="contradictionDetailArea"></div>' not in content
    assert "detailArea.scrollIntoView" not in content
