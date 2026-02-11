"""Tests for searchat.core lazy imports."""
from __future__ import annotations

import pytest


class TestCoreGetattr:
    """Tests for searchat.core.__getattr__ lazy loading."""

    def test_search_engine_lazy_import(self):
        import searchat.core as core
        engine_cls = core.SearchEngine
        assert engine_cls is not None
        assert engine_cls.__name__ == "SearchEngine"

    def test_unknown_attribute_raises(self):
        import searchat.core as core
        with pytest.raises(AttributeError, match="has no attribute"):
            _ = core.NonexistentThing
