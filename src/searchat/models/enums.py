"""Enumerations for searchat."""
from __future__ import annotations

from enum import Enum


class SearchMode(Enum):
    """Search mode for querying conversations."""
    KEYWORD = "keyword"
    SEMANTIC = "semantic"
    HYBRID = "hybrid"


class AlgorithmType(Enum):
    """Algorithm type for the unified search engine.

    KEYWORD, SEMANTIC, HYBRID mirror SearchMode for backward compatibility.
    ADAPTIVE selects weights via QueryClassifier per-query.
    CROSS_LAYER and DISTILL are Phase 6 stubs (return 400 until Palace lands).
    """
    KEYWORD = "keyword"
    SEMANTIC = "semantic"
    HYBRID = "hybrid"
    ADAPTIVE = "adaptive"
    CROSS_LAYER = "cross_layer"
    DISTILL = "distill"

    def to_search_mode(self) -> SearchMode:
        """Map to legacy SearchMode where applicable."""
        _map = {
            AlgorithmType.KEYWORD: SearchMode.KEYWORD,
            AlgorithmType.SEMANTIC: SearchMode.SEMANTIC,
            AlgorithmType.HYBRID: SearchMode.HYBRID,
            AlgorithmType.ADAPTIVE: SearchMode.HYBRID,
        }
        return _map.get(self, SearchMode.HYBRID)

    @classmethod
    def from_search_mode(cls, mode: SearchMode) -> AlgorithmType:
        """Map legacy SearchMode to AlgorithmType."""
        return cls(mode.value)
