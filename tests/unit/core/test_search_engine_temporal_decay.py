from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from searchat.config import Config
from searchat.core.search_engine import SearchEngine
from searchat.models.domain import SearchResult


@pytest.mark.unit
def test_temporal_decay_can_change_merge_order(temp_search_dir: Path):
    cfg = Config.load()
    cfg.search.temporal_decay_enabled = True
    cfg.search.temporal_decay_factor = 0.01
    cfg.search.temporal_weight = 1.0

    (temp_search_dir / "data" / "conversations").mkdir(parents=True, exist_ok=True)
    (temp_search_dir / "data" / "conversations" / "c.parquet").write_bytes(b"")
    engine = SearchEngine(temp_search_dir, cfg)

    now = datetime.now(timezone.utc)
    old = now - timedelta(days=365)

    dummy = SearchResult(
        conversation_id="dummy",
        project_id="p",
        title="d",
        created_at=old,
        updated_at=old,
        message_count=1,
        file_path="/tmp/d",
        score=1.0,
        snippet="",
    )

    older_high = SearchResult(
        conversation_id="older",
        project_id="p",
        title="o",
        created_at=old,
        updated_at=old,
        message_count=1,
        file_path="/tmp/o",
        score=10.0,
        snippet="",
    )

    newer_slightly_lower = SearchResult(
        conversation_id="newer",
        project_id="p",
        title="n",
        created_at=now,
        updated_at=now,
        message_count=1,
        file_path="/tmp/n",
        score=9.5,
        snippet="",
    )

    merged = engine._merge_results(
        keyword=[older_high, newer_slightly_lower, dummy],
        semantic=[],
    )

    assert merged[0].conversation_id == "newer"


@pytest.mark.unit
def test_temporal_decay_disabled_preserves_base_order(temp_search_dir: Path):
    cfg = Config.load()
    cfg.search.temporal_decay_enabled = False
    cfg.search.temporal_decay_factor = 0.01
    cfg.search.temporal_weight = 1.0

    (temp_search_dir / "data" / "conversations").mkdir(parents=True, exist_ok=True)
    (temp_search_dir / "data" / "conversations" / "c.parquet").write_bytes(b"")
    engine = SearchEngine(temp_search_dir, cfg)

    now = datetime.now(timezone.utc)
    old = now - timedelta(days=365)

    dummy = SearchResult(
        conversation_id="dummy",
        project_id="p",
        title="d",
        created_at=old,
        updated_at=old,
        message_count=1,
        file_path="/tmp/d",
        score=1.0,
        snippet="",
    )

    older_high = SearchResult(
        conversation_id="older",
        project_id="p",
        title="o",
        created_at=old,
        updated_at=old,
        message_count=1,
        file_path="/tmp/o",
        score=10.0,
        snippet="",
    )

    newer_slightly_lower = SearchResult(
        conversation_id="newer",
        project_id="p",
        title="n",
        created_at=now,
        updated_at=now,
        message_count=1,
        file_path="/tmp/n",
        score=9.5,
        snippet="",
    )

    merged = engine._merge_results(
        keyword=[older_high, newer_slightly_lower, dummy],
        semantic=[],
    )

    assert merged[0].conversation_id == "older"
