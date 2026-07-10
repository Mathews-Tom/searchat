"""Regression test for the bookmarks page XSS fix.

`bookmarks.js` renders `bookmark.title` / `bookmark.project_id` via
`div.innerHTML = ...` template literals. Those fields are sourced from the indexed
conversation's `title` (the first message's raw text, verbatim -- see
`core/connectors/claude.py`) and `project_id`, both fully attacker/
content-controlled. Every other rendering module in this codebase
(`manage.js`, `search.js`, `chat.js`, ...) escapes such fields through a
local `escapeHtml()` helper before interpolating them into `innerHTML`;
`bookmarks.js` used to be the one exception. A live headless-browser
reproduction confirmed the pre-fix template executed a crafted
`<img onerror=...>` payload verbatim, and that the post-fix template
renders it as inert escaped text.
"""
from __future__ import annotations

from pathlib import Path

WEB_ROOT = Path(__file__).parents[2] / "src" / "searchat" / "web"
BOOKMARKS_JS = WEB_ROOT / "static" / "js" / "modules" / "bookmarks.js"


def _source() -> str:
    return BOOKMARKS_JS.read_text(encoding="utf-8")


def test_bookmarks_js_exists() -> None:
    assert BOOKMARKS_JS.exists(), "bookmarks.js module must exist"


def test_bookmarks_js_defines_escape_helper() -> None:
    source = _source()
    assert "function escapeHtml(" in source, (
        "bookmarks.js must define an escapeHtml() helper, matching the "
        "convention used by every other rendering module"
    )


def test_bookmarks_js_escapes_title_before_innerhtml() -> None:
    source = _source()
    assert "escapeHtml(bookmark.title)" in source, (
        "bookmark.title is attacker/content-controlled (first message text) "
        "and must be escaped before interpolation into innerHTML"
    )


def test_bookmarks_js_escapes_project_id_before_innerhtml() -> None:
    source = _source()
    assert "escapeHtml(bookmark.project_id)" in source, (
        "bookmark.project_id is attacker-influenceable (source directory "
        "name) and must be escaped before interpolation into innerHTML"
    )


def test_bookmarks_js_never_interpolates_raw_title_into_innerhtml() -> None:
    source = _source()
    assert "${bookmark.title || 'Untitled'}" not in source, (
        "raw unescaped bookmark.title must not be interpolated directly "
        "into an innerHTML template literal"
    )
