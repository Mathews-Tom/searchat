"""FastAPI application package for Searchat."""

from __future__ import annotations

from typing import Any

__all__ = ["app", "main"]


def __getattr__(name: str) -> Any:
    if name in {"app", "main"}:
        from searchat.api.app import app, main

        exports = {"app": app, "main": main}
        return exports[name]
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
