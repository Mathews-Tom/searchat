"""Tests verifying expertise dashboard assets are present and correctly referenced."""
from __future__ import annotations

from pathlib import Path

import pytest

WEB_ROOT = Path(__file__).parents[2] / "src" / "searchat" / "web"
INDEX_HTML = WEB_ROOT / "index.html"
MAIN_JS = WEB_ROOT / "static" / "js" / "main.js"
EXPERTISE_JS = WEB_ROOT / "static" / "js" / "modules" / "expertise.js"
CONTRADICTIONS_JS = WEB_ROOT / "static" / "js" / "modules" / "contradictions.js"
EXPERTISE_CSS = WEB_ROOT / "static" / "css" / "expertise.css"


# ── File existence ────────────────────────────────────────────────────────────


def test_expertise_js_exists() -> None:
    assert EXPERTISE_JS.exists(), "expertise.js module must exist"


def test_contradictions_js_exists() -> None:
    assert CONTRADICTIONS_JS.exists(), "contradictions.js module must exist"


def test_expertise_css_exists() -> None:
    assert EXPERTISE_CSS.exists(), "expertise.css stylesheet must exist"


# ── index.html markup ────────────────────────────────────────────────────────


@pytest.fixture(scope="module")
def index_html() -> str:
    return INDEX_HTML.read_text(encoding="utf-8")


def test_expertise_css_linked(index_html: str) -> None:
    assert "expertise.css" in index_html, "index.html must link expertise.css"


def test_expertise_nav_item_present(index_html: str) -> None:
    assert 'data-action="showExpertise"' in index_html, (
        "index.html must have a nav item with data-action=showExpertise"
    )


def test_contradictions_nav_item_present(index_html: str) -> None:
    assert 'data-action="showContradictions"' in index_html, (
        "index.html must have a nav item with data-action=showContradictions"
    )


def test_expertise_toolbar_button_present(index_html: str) -> None:
    assert 'id="expertiseButton"' in index_html, (
        "index.html must have toolbar button with id=expertiseButton"
    )


def test_contradictions_toolbar_button_present(index_html: str) -> None:
    assert 'id="contradictionsButton"' in index_html, (
        "index.html must have toolbar button with id=contradictionsButton"
    )


# ── main.js imports ──────────────────────────────────────────────────────────


@pytest.fixture(scope="module")
def main_js() -> str:
    return MAIN_JS.read_text(encoding="utf-8")


def test_main_js_imports_expertise(main_js: str) -> None:
    assert "showExpertise" in main_js, "main.js must import showExpertise"


def test_main_js_imports_contradictions(main_js: str) -> None:
    assert "showContradictions" in main_js, "main.js must import showContradictions"


def test_main_js_exposes_expertise_globally(main_js: str) -> None:
    assert "window.showExpertise" in main_js, (
        "main.js must expose showExpertise on window"
    )


def test_main_js_exposes_contradictions_globally(main_js: str) -> None:
    assert "window.showContradictions" in main_js, (
        "main.js must expose showContradictions on window"
    )


# ── expertise.js content ─────────────────────────────────────────────────────


@pytest.fixture(scope="module")
def expertise_js() -> str:
    return EXPERTISE_JS.read_text(encoding="utf-8")


def test_expertise_js_exports_show_expertise(expertise_js: str) -> None:
    assert "export async function showExpertise" in expertise_js, (
        "expertise.js must export showExpertise"
    )


def test_expertise_js_fetches_status_endpoint(expertise_js: str) -> None:
    assert "/api/expertise/status" in expertise_js, (
        "expertise.js must call /api/expertise/status"
    )


def test_expertise_js_fetches_domains_endpoint(expertise_js: str) -> None:
    assert "/api/expertise/domains" in expertise_js, (
        "expertise.js must call /api/expertise/domains"
    )


def test_expertise_js_fetches_records_endpoint(expertise_js: str) -> None:
    assert "/api/expertise?" in expertise_js, (
        "expertise.js must call /api/expertise with query params"
    )


def test_expertise_js_fetches_lineage_endpoint(expertise_js: str) -> None:
    assert "/api/knowledge-graph/lineage/" in expertise_js, (
        "expertise.js must call /api/knowledge-graph/lineage/{id}"
    )


def test_expertise_js_has_domain_health_table(expertise_js: str) -> None:
    assert "expertise-table" in expertise_js, (
        "expertise.js must render domain health table"
    )


def test_expertise_js_has_health_badge(expertise_js: str) -> None:
    assert "health-badge" in expertise_js, (
        "expertise.js must render health badges"
    )


def test_expertise_js_has_pagination(expertise_js: str) -> None:
    assert "PAGE_SIZE" in expertise_js, "expertise.js must implement pagination"


def test_expertise_js_has_record_detail(expertise_js: str) -> None:
    assert "expertise-detail-panel" in expertise_js, (
        "expertise.js must render record detail panel"
    )


# ── contradictions.js content ────────────────────────────────────────────────


@pytest.fixture(scope="module")
def contradictions_js() -> str:
    return CONTRADICTIONS_JS.read_text(encoding="utf-8")


def test_contradictions_js_exports_show_contradictions(contradictions_js: str) -> None:
    assert "export async function showContradictions" in contradictions_js, (
        "contradictions.js must export showContradictions"
    )


def test_contradictions_js_fetches_contradictions_endpoint(contradictions_js: str) -> None:
    assert "/api/knowledge-graph/contradictions" in contradictions_js, (
        "contradictions.js must call /api/knowledge-graph/contradictions"
    )


def test_contradictions_js_fetches_stats_endpoint(contradictions_js: str) -> None:
    assert "/api/knowledge-graph/stats" in contradictions_js, (
        "contradictions.js must call /api/knowledge-graph/stats"
    )


def test_contradictions_js_posts_resolve_endpoint(contradictions_js: str) -> None:
    assert "/api/knowledge-graph/resolve" in contradictions_js, (
        "contradictions.js must POST to /api/knowledge-graph/resolve"
    )


def test_contradictions_js_has_comparison_layout(contradictions_js: str) -> None:
    assert "contradiction-comparison" in contradictions_js, (
        "contradictions.js must render side-by-side comparison layout"
    )


def test_contradictions_js_has_resolution_strategies(contradictions_js: str) -> None:
    for strategy in ("supersede", "scope_both", "merge", "dismiss", "keep_both"):
        assert strategy in contradictions_js, (
            f"contradictions.js must support resolution strategy: {strategy}"
        )


def test_contradictions_js_has_health_score_display(contradictions_js: str) -> None:
    assert "health_score" in contradictions_js, (
        "contradictions.js must display health_score from stats"
    )


# ── expertise.css content ────────────────────────────────────────────────────


@pytest.fixture(scope="module")
def expertise_css() -> str:
    return EXPERTISE_CSS.read_text(encoding="utf-8")


def test_expertise_css_has_health_badge_styles(expertise_css: str) -> None:
    assert ".health-badge" in expertise_css, "expertise.css must define .health-badge"


def test_expertise_css_has_health_variants(expertise_css: str) -> None:
    for variant in ("--healthy", "--warning", "--critical"):
        assert f"health-badge{variant}" in expertise_css, (
            f"expertise.css must define .health-badge{variant}"
        )


def test_expertise_css_has_contradiction_comparison(expertise_css: str) -> None:
    assert ".contradiction-comparison" in expertise_css, (
        "expertise.css must define .contradiction-comparison layout"
    )


def test_expertise_css_has_record_item_styles(expertise_css: str) -> None:
    assert ".expertise-record-item" in expertise_css, (
        "expertise.css must define .expertise-record-item"
    )


def test_expertise_css_uses_css_variables(expertise_css: str) -> None:
    assert "hsl(var(--" in expertise_css, (
        "expertise.css must use CSS custom properties from variables.css"
    )


def test_expertise_css_has_table_styles(expertise_css: str) -> None:
    assert ".expertise-table" in expertise_css, (
        "expertise.css must define .expertise-table styles"
    )
