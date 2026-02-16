from __future__ import annotations

from pathlib import Path


def test_dashboards_ui_references_expected_endpoints() -> None:
    dashboards_js = (
        Path(__file__).resolve().parents[2]
        / "src"
        / "searchat"
        / "web"
        / "static"
        / "js"
        / "modules"
        / "dashboards.js"
    )
    content = dashboards_js.read_text(encoding="utf-8")
    assert "/api/status/features" in content
    assert "/api/dashboards" in content
    assert "/render" in content
    assert "method: 'PUT'" in content
    assert "builder-save" in content
    assert "dashboard-builder" in content
    assert "dashboard-grid" in content


def test_index_html_exposes_dashboards_entry_point() -> None:
    index_html = Path(__file__).resolve().parents[2] / "src" / "searchat" / "web" / "index.html"
    content = index_html.read_text(encoding="utf-8")
    assert "showDashboards" in content
