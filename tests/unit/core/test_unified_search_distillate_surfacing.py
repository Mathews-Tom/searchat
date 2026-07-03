"""M9 search-layer surfacing: DISTILL/CROSS_LAYER hits carry
`is_distillate=True` so a caller knows to offer an "expand to verbatim"
affordance (`services.distillation_bridge.rehydrate_verbatim`), while
ordinary hot-index hits stay `is_distillate=False`.
"""
from __future__ import annotations

from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq
import pytest

from searchat.config import Config
from searchat.core.unified_search import UnifiedSearchEngine
from searchat.models import CONVERSATION_SCHEMA
from searchat.models.domain import FileTouched, PalaceSearchResult, SearchResult


def _make_engine(tmp_path: Path) -> UnifiedSearchEngine:
    search_dir = tmp_path / "search"
    conversations_dir = search_dir / "data" / "conversations"
    conversations_dir.mkdir(parents=True)
    table = pa.Table.from_pylist([], schema=CONVERSATION_SCHEMA)
    pq.write_table(table, conversations_dir / "project_empty.parquet")
    config = Config.load()
    config.palace.enabled = True
    return UnifiedSearchEngine(search_dir, config)


class _FakePalaceQuery:
    def __init__(self, hybrid_results: list[PalaceSearchResult]) -> None:
        self._hybrid_results = hybrid_results

    def search_hybrid(self, query: str, limit: int = 50, project_ids=None, **kwargs):
        return self._hybrid_results


def _palace_result(conversation_id: str, object_id: str = "obj-1") -> PalaceSearchResult:
    return PalaceSearchResult(
        object_id=object_id,
        conversation_id=conversation_id,
        project_id="proj-1",
        ply_start=0,
        ply_end=1,
        exchange_core="distilled summary",
        specific_context="some specific detail",
        files_touched=[FileTouched(path="a.py", action="modified")],
        rooms=[],
        score=0.9,
        keyword_score=0.5,
        semantic_score=0.7,
    )


class TestDistillSearchMarksResultsAsDistillate:
    def test_distill_search_results_are_marked_is_distillate(self, tmp_path: Path):
        engine = _make_engine(tmp_path)
        engine._palace_query = _FakePalaceQuery([_palace_result("conv-1")])

        results, mode_used = engine._distill_search("anything", None)

        assert mode_used == "distill"
        assert len(results) == 1
        assert results[0].is_distillate is True
        assert results[0].conversation_id == "conv-1"


class TestCrossLayerSearchDistillateFlagging:
    def test_palace_only_hit_is_marked_is_distillate(self, tmp_path: Path):
        engine = _make_engine(tmp_path)
        engine._palace_query = _FakePalaceQuery([_palace_result("conv-evicted")])

        results, mode_used = engine._cross_layer_search("anything", None)

        assert mode_used == "cross_layer"
        assert len(results) == 1
        assert results[0].conversation_id == "conv-evicted"
        assert results[0].is_distillate is True

    def test_verbatim_hit_boosted_by_palace_stays_not_distillate(self, tmp_path: Path, monkeypatch):
        engine = _make_engine(tmp_path)
        verbatim_hit = SearchResult(
            conversation_id="conv-hot",
            project_id="proj-1",
            title="hot conversation",
            created_at=None,  # type: ignore[arg-type]
            updated_at=None,  # type: ignore[arg-type]
            message_count=2,
            file_path="",
            score=0.5,
            snippet="verbatim snippet",
            exchange_id="exc-1",
            exchange_text="verbatim exchange text",
        )
        monkeypatch.setattr(engine, "_hybrid_search", lambda query, filters: ([verbatim_hit], "hybrid"))
        engine._palace_query = _FakePalaceQuery([_palace_result("conv-hot")])

        results, _ = engine._cross_layer_search("anything", None)

        assert len(results) == 1
        assert results[0].conversation_id == "conv-hot"
        assert results[0].is_distillate is False
        assert results[0].score == pytest.approx(0.5 * 1.3)


class TestDefaultSearchResultIsNotDistillate:
    def test_default_is_distillate_is_false(self):
        result = SearchResult(
            conversation_id="c", project_id="p", title="t",
            created_at=None, updated_at=None,  # type: ignore[arg-type]
            message_count=1, file_path="", score=1.0, snippet="s",
        )
        assert result.is_distillate is False
