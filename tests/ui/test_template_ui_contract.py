from __future__ import annotations

from pathlib import Path


def test_live_page_templates_do_not_bootstrap_fragment_routes() -> None:
    templates_dir = (
        Path(__file__).resolve().parents[2]
        / "src"
        / "searchat"
        / "web"
        / "templates"
    )

    live_templates = [
        templates_dir / "index.html",
        templates_dir / "manage.html",
        templates_dir / "conversation.html",
        templates_dir / "chat.html",
    ]

    for template_path in live_templates:
        content = template_path.read_text(encoding="utf-8")
        assert "/fragments/" not in content, template_path.name
