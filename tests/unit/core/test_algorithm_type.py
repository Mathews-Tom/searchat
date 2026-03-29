"""Tests for AlgorithmType enum and SearchMode interop."""
from __future__ import annotations

import pytest

from searchat.models.enums import AlgorithmType, SearchMode


class TestAlgorithmType:
    def test_six_values(self) -> None:
        assert len(AlgorithmType) == 6

    def test_values_match_expected(self) -> None:
        expected = {"keyword", "semantic", "hybrid", "adaptive", "cross_layer", "distill"}
        assert {a.value for a in AlgorithmType} == expected

    def test_from_search_mode_roundtrip(self) -> None:
        for mode in SearchMode:
            algo = AlgorithmType.from_search_mode(mode)
            assert algo.value == mode.value

    def test_to_search_mode_for_base_types(self) -> None:
        assert AlgorithmType.KEYWORD.to_search_mode() == SearchMode.KEYWORD
        assert AlgorithmType.SEMANTIC.to_search_mode() == SearchMode.SEMANTIC
        assert AlgorithmType.HYBRID.to_search_mode() == SearchMode.HYBRID

    def test_adaptive_maps_to_hybrid(self) -> None:
        assert AlgorithmType.ADAPTIVE.to_search_mode() == SearchMode.HYBRID

    def test_cross_layer_maps_to_hybrid(self) -> None:
        assert AlgorithmType.CROSS_LAYER.to_search_mode() == SearchMode.HYBRID

    def test_distill_maps_to_hybrid(self) -> None:
        assert AlgorithmType.DISTILL.to_search_mode() == SearchMode.HYBRID
