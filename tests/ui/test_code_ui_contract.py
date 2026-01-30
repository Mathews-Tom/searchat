from __future__ import annotations

from pathlib import Path


def test_code_extraction_js_references_highlight_endpoint():
    code_js = (
        Path(__file__).resolve().parents[2]
        / "src"
        / "searchat"
        / "web"
        / "static"
        / "js"
        / "modules"
        / "code-extraction.js"
    )
    content = code_js.read_text(encoding="utf-8")
    assert "/api/code/highlight" in content
