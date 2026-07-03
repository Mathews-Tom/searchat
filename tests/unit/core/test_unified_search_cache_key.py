"""Regression test: UnifiedSearchEngine cache keys must be tool-filter aware.

Surfaced while testing the omp connector's tool=omp search filter: two
searches with the same query but different `filters.tool` values produced
the same cache key, so the second query silently returned the first
query's (wrong-tool) cached results.
"""
from __future__ import annotations

from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq

from searchat.config import Config
from searchat.core.unified_search import UnifiedSearchEngine
from searchat.models import AlgorithmType, CONVERSATION_SCHEMA, SearchFilters


def _make_engine(tmp_path: Path) -> UnifiedSearchEngine:
    search_dir = tmp_path / "search"
    conversations_dir = search_dir / "data" / "conversations"
    conversations_dir.mkdir(parents=True)
    table = pa.Table.from_pylist([], schema=CONVERSATION_SCHEMA)
    pq.write_table(table, conversations_dir / "project_empty.parquet")
    return UnifiedSearchEngine(search_dir, Config.load())


def test_cache_key_differs_by_tool_filter(tmp_path: Path) -> None:
    engine = _make_engine(tmp_path)

    key_omp = engine._get_cache_key("*", AlgorithmType.KEYWORD, SearchFilters(tool="omp"))
    key_claude = engine._get_cache_key("*", AlgorithmType.KEYWORD, SearchFilters(tool="claude"))
    key_none = engine._get_cache_key("*", AlgorithmType.KEYWORD, None)

    assert key_omp != key_claude
    assert key_omp != key_none
    assert key_claude != key_none


def test_cache_key_stable_for_same_filters(tmp_path: Path) -> None:
    engine = _make_engine(tmp_path)

    key_a = engine._get_cache_key("*", AlgorithmType.KEYWORD, SearchFilters(tool="omp"))
    key_b = engine._get_cache_key("*", AlgorithmType.KEYWORD, SearchFilters(tool="omp"))

    assert key_a == key_b
