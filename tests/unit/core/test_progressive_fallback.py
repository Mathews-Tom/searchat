"""Tests for the progressive fallback component."""
from __future__ import annotations

from searchat.core.progressive_fallback import FallbackResult, ProgressiveFallback
from searchat.models.domain import SearchResult


def _make_results(n: int) -> list[SearchResult]:
    from datetime import datetime
    return [
        SearchResult(
            conversation_id=str(i),
            project_id="p",
            title=f"Title {i}",
            created_at=datetime(2024, 1, 1),
            updated_at=datetime(2024, 1, 1),
            message_count=10,
            file_path=f"/{i}.jsonl",
            score=1.0,
            snippet="s",
        )
        for i in range(n)
    ]


class TestProgressiveFallback:
    def test_first_tier_succeeds(self) -> None:
        fb = ProgressiveFallback()
        results = _make_results(3)
        outcome = fb.execute([
            ("hybrid", lambda: results),
            ("keyword", lambda: _make_results(1)),
        ])
        assert outcome.tier_used == 1
        assert outcome.mode_used == "hybrid"
        assert len(outcome.results) == 3
        assert outcome.errors == []

    def test_fallback_to_second_tier(self) -> None:
        fb = ProgressiveFallback()
        fallback_results = _make_results(2)

        def fail_tier():
            raise RuntimeError("semantic unavailable")

        outcome = fb.execute([
            ("hybrid", fail_tier),
            ("keyword", lambda: fallback_results),
        ])
        assert outcome.tier_used == 2
        assert outcome.mode_used == "keyword"
        assert len(outcome.results) == 2
        assert len(outcome.errors) == 1
        assert "semantic unavailable" in outcome.errors[0]

    def test_all_tiers_fail(self) -> None:
        fb = ProgressiveFallback()

        def fail1():
            raise RuntimeError("fail1")

        def fail2():
            raise RuntimeError("fail2")

        outcome = fb.execute([("tier1", fail1), ("tier2", fail2)])
        assert outcome.tier_used == 0
        assert outcome.mode_used == "none"
        assert outcome.results == []
        assert len(outcome.errors) == 2

    def test_empty_tiers(self) -> None:
        fb = ProgressiveFallback()
        outcome = fb.execute([])
        assert outcome.tier_used == 0
        assert outcome.results == []
