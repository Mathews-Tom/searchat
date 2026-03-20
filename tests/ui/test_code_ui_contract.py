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


def test_code_extraction_copy_button_uses_bound_listener_contract() -> None:
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

    assert 'class="code-copy-trigger"' in content
    assert "data-copy-index" in content
    assert "container.querySelectorAll('.code-copy-trigger').forEach" in content
    assert "copyCode(index, btn);" in content
    assert "window.copyCode(" not in content
    assert "onclick=" not in content


def test_search_snippet_copy_button_uses_icon_and_state_classes() -> None:
    search_js = (
        Path(__file__).resolve().parents[2]
        / "src"
        / "searchat"
        / "web"
        / "static"
        / "js"
        / "modules"
        / "search.js"
    )
    content = search_js.read_text(encoding="utf-8")

    assert 'class="snippet-copy"' in content
    assert "copyIconSvg()" in content
    assert "checkIconSvg()" in content
    assert "snippetCopyBtn.classList.add('is-copied')" in content


def test_code_highlighting_contract_skips_plaintext_guessing_and_error_borders() -> None:
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
    pygments_css = (
        Path(__file__).resolve().parents[2]
        / "src"
        / "searchat"
        / "web"
        / "static"
        / "css"
        / "pygments.css"
    )

    code_content = code_js.read_text(encoding="utf-8")
    css_content = pygments_css.read_text(encoding="utf-8")

    assert "['plaintext', 'text', 'plain'].includes(normalizedLanguage)" in code_content
    assert ".pygments .err { border: 0;" in css_content


def test_clearable_input_module_is_initialized_from_legacy_bootstrap() -> None:
    main_js = (
        Path(__file__).resolve().parents[2]
        / "src"
        / "searchat"
        / "web"
        / "static"
        / "js"
        / "main.js"
    )
    clearable_js = (
        Path(__file__).resolve().parents[2]
        / "src"
        / "searchat"
        / "web"
        / "static"
        / "js"
        / "modules"
        / "clearable-inputs.js"
    )

    main_content = main_js.read_text(encoding="utf-8")
    clearable_content = clearable_js.read_text(encoding="utf-8")

    assert "import { initClearableInputs } from './modules/clearable-inputs.js';" in main_content
    assert "safeInit('clearable-inputs', initClearableInputs);" in main_content
    assert "const CLEARABLE_SELECTOR = 'input[type=\"text\"], input[type=\"search\"], textarea';" in clearable_content
    assert "field.dispatchEvent(new Event('input', { bubbles: true }));" in clearable_content


def test_bookmark_icon_uses_svg_and_themeable_state_classes() -> None:
    bookmark_js = (
        Path(__file__).resolve().parents[2]
        / "src"
        / "searchat"
        / "web"
        / "static"
        / "js"
        / "modules"
        / "bookmarks.js"
    )
    components_css = (
        Path(__file__).resolve().parents[2]
        / "src"
        / "searchat"
        / "web"
        / "static"
        / "css"
        / "components.css"
    )

    js_content = bookmark_js.read_text(encoding="utf-8")
    css_content = components_css.read_text(encoding="utf-8")

    assert "function bookmarkIconSvg(isBookmarked)" in js_content
    assert "element.innerHTML = bookmarkIconSvg(true);" in js_content
    assert "element.classList.add('active');" in js_content
    assert ".bookmark-star {" in css_content
    assert ".bookmark-star.active {" in css_content
