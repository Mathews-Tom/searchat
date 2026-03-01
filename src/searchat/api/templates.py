"""Jinja2 template configuration for Searchat web UI."""
from __future__ import annotations

import hashlib
from pathlib import Path

from fastapi.templating import Jinja2Templates

_WEB_DIR = Path(__file__).parent.parent / "web"
_STATIC_DIR = _WEB_DIR / "static"
_TEMPLATE_DIR = _WEB_DIR / "templates"

templates = Jinja2Templates(directory=str(_TEMPLATE_DIR))


def _static_fingerprint() -> str:
    """Hash the combined mtime of every file under web/static/.

    Changes on any JS/CSS/asset edit, no version bump needed.
    """
    h = hashlib.md5(usedforsecurity=False)
    for p in sorted(_STATIC_DIR.rglob("*")):
        if p.is_file():
            h.update(
                f"{p.relative_to(_STATIC_DIR)}:{p.stat().st_mtime_ns}".encode()
            )
    return h.hexdigest()[:10]


# Compute once at import time; changes require server restart.
_FINGERPRINT = _static_fingerprint()


def static_url(path: str) -> str:
    """Return a cache-busted static URL.

    Usage in Jinja2: {{ static_url('/static/css/base.css') }}
    Output:          /static/css/base.css?v=abc123def4
    """
    if "?" in path:
        return path
    return f"{path}?v={_FINGERPRINT}"


# Register as a Jinja2 global so all templates can use it.
templates.env.globals["static_url"] = static_url
