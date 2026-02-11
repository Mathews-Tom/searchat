"""Tests for searchat package-level lazy imports."""
from __future__ import annotations

import pytest


class TestPackageGetattr:
    """Tests for searchat.__getattr__ lazy loading."""

    def test_search_engine_lazy_import(self):
        import searchat
        engine_cls = searchat.SearchEngine
        assert engine_cls.__name__ == "SearchEngine"

    def test_unknown_attribute_raises(self):
        import searchat
        with pytest.raises(AttributeError, match="has no attribute"):
            _ = searchat.NonexistentThing
