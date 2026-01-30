from __future__ import annotations

from pathlib import Path


def test_analytics_js_contains_range_filter_and_new_endpoints():
    analytics_js = (
        Path(__file__).resolve().parents[2]
        / "src"
        / "searchat"
        / "web"
        / "static"
        / "js"
        / "modules"
        / "analytics.js"
    )
    content = analytics_js.read_text(encoding="utf-8")

    assert "/api/stats/analytics/trends" in content
    assert "/api/stats/analytics/heatmap" in content
    assert "/api/stats/analytics/agent-comparison" in content
    assert "/api/stats/analytics/topics" in content

    assert "id=\"analyticsDays\"" in content
    assert "id=\"analyticsRefresh\"" in content
