"""Tests for the CombMNZ result merger."""
from __future__ import annotations

from datetime import datetime

import pytest

from searchat.core.result_merger import MergeConfig, ResultMerger, _percentile_normalize
from searchat.models.domain import SearchResult


def _make_result(cid: str, score: float = 1.0) -> SearchResult:
    return SearchResult(
        conversation_id=cid,
        project_id="proj",
        title=f"Title {cid}",
        created_at=datetime(2024, 1, 1),
        updated_at=datetime(2024, 1, 1),
        message_count=10,
        file_path=f"/path/{cid}.jsonl",
        score=score,
        snippet="snippet",
    )


class TestPercentileNormalize:
    def test_empty_list(self) -> None:
        assert _percentile_normalize([]) == {}

    def test_single_item(self) -> None:
        results = [_make_result("a", 5.0)]
        scores = _percentile_normalize(results)
        assert scores["a"] == 1.0

    def test_preserves_rank_order(self) -> None:
        results = [_make_result("a", 10.0), _make_result("b", 5.0), _make_result("c", 1.0)]
        scores = _percentile_normalize(results)
        assert scores["a"] > scores["b"] > scores["c"]

    def test_three_items_correct_values(self) -> None:
        results = [_make_result("a"), _make_result("b"), _make_result("c")]
        scores = _percentile_normalize(results)
        # rank 0 → 3/3=1.0, rank 1 → 2/3≈0.667, rank 2 → 1/3≈0.333
        assert abs(scores["a"] - 1.0) < 0.01
        assert abs(scores["b"] - 2 / 3) < 0.01
        assert abs(scores["c"] - 1 / 3) < 0.01


class TestResultMerger:
    @pytest.fixture()
    def merger(self) -> ResultMerger:
        return ResultMerger(MergeConfig(
            keyword_weight=0.6,
            semantic_weight=0.4,
            intersection_boost=1.5,
            max_results=10,
        ))

    def test_empty_inputs(self, merger: ResultMerger) -> None:
        assert merger.merge([], []) == []

    def test_keyword_only(self, merger: ResultMerger) -> None:
        kw = [_make_result("a", 10.0), _make_result("b", 5.0)]
        results = merger.merge(kw, [])
        assert len(results) == 2
        assert results[0].conversation_id == "a"

    def test_semantic_only(self, merger: ResultMerger) -> None:
        sem = [_make_result("x", 0.9), _make_result("y", 0.5)]
        results = merger.merge([], sem)
        assert len(results) == 2
        assert results[0].conversation_id == "x"

    def test_intersection_boosted(self, merger: ResultMerger) -> None:
        kw = [_make_result("shared", 10.0), _make_result("kw_only", 8.0)]
        sem = [_make_result("shared", 0.9), _make_result("sem_only", 0.7)]
        results = merger.merge(kw, sem)
        # "shared" should be first due to intersection boost
        assert results[0].conversation_id == "shared"

    def test_bm25_and_semantic_scores_populated(self, merger: ResultMerger) -> None:
        kw = [_make_result("a", 10.0)]
        sem = [_make_result("a", 0.9)]
        results = merger.merge(kw, sem)
        assert results[0].bm25_score is not None
        assert results[0].semantic_score is not None

    def test_max_results_honored(self) -> None:
        merger = ResultMerger(MergeConfig(max_results=3))
        kw = [_make_result(str(i)) for i in range(10)]
        results = merger.merge(kw, [])
        assert len(results) <= 3

    def test_custom_weights_override(self, merger: ResultMerger) -> None:
        kw = [_make_result("a", 10.0)]
        sem = [_make_result("b", 0.9)]
        results = merger.merge(kw, sem, keyword_weight=0.1, semantic_weight=0.9)
        # With 0.9 semantic weight, "b" should rank higher
        assert results[0].conversation_id == "b"
