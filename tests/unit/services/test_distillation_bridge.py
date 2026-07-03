"""Unit tests for `searchat.services.distillation_bridge` (M9).

Coverage map:
- `TestSelectDistillationCandidates` -- age-based candidate selection,
  palace-independent.

Later commits/PRs in this stack add distillate generation, hot-index
eviction, the promotion path, the end-to-end orchestrator, and the
fixture-benchmark acceptance tests.
"""
from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path

from searchat.core.unified_indexer import _segment_exchanges
from searchat.services import distillation_bridge
from searchat.storage.unified_storage import UnifiedStorage

import pytest

# ---------------------------------------------------------------------------
# Shared fixtures / helpers
# ---------------------------------------------------------------------------


@pytest.fixture()
def storage(tmp_path: Path):
    s = UnifiedStorage(tmp_path / "unified.duckdb")
    yield s
    s.close()


def _insert_conversation(
    storage: UnifiedStorage,
    *,
    conversation_id: str,
    project_id: str = "proj-1",
    updated_at: datetime,
    messages: list[dict],
) -> None:
    storage.upsert_conversation(
        conversation_id=conversation_id,
        project_id=project_id,
        file_path=f"/data/{conversation_id}.jsonl",
        title=conversation_id,
        created_at=updated_at,
        updated_at=updated_at,
        message_count=len(messages),
        full_text=" ".join(m["content"] for m in messages),
        file_hash="hash",
        indexed_at=updated_at,
    )
    storage.insert_messages(conversation_id, messages)


def _make_messages(num_exchanges: int, *, min_len: int = 60) -> list[dict]:
    """Real user/assistant message pairs, long enough to clear
    `Distiller`'s own `min_exchange_chars` filter (default 50)."""
    messages: list[dict] = []
    seq = 0
    base = datetime(2025, 1, 1)
    for i in range(num_exchanges):
        messages.append({
            "sequence": seq,
            "role": "user",
            "content": f"Question {i}: what should I do about issue number {i}?",
            "timestamp": base,
            "has_code": False,
            "code_blocks": None,
        })
        seq += 1
        filler = "x" * max(0, min_len - 20)
        messages.append({
            "sequence": seq,
            "role": "assistant",
            "content": f"Answer {i}: do this instead. {filler}",
            "timestamp": base,
            "has_code": False,
            "code_blocks": None,
        })
        seq += 1
    return messages


def _seed_hot_exchanges(storage: UnifiedStorage, conversation_id: str, project_id: str, messages: list[dict]) -> list[dict]:
    """Populate `exchanges`/`verbatim_embeddings` the way indexing would,
    using the real M2 segmentation function (`_segment_exchanges`)."""
    exchanges = _segment_exchanges(conversation_id, project_id, messages, messages[0]["timestamp"])
    for exc in exchanges:
        storage.upsert_exchange(**exc)
        storage.upsert_embedding(exc["exchange_id"], [0.1] * 384)
    return exchanges


# ---------------------------------------------------------------------------
# 1. Candidate selection
# ---------------------------------------------------------------------------


class TestSelectDistillationCandidates:
    def test_old_conversation_with_hot_exchanges_is_a_candidate(self, storage: UnifiedStorage):
        now = datetime(2026, 1, 1)
        messages = _make_messages(1)
        _insert_conversation(storage, conversation_id="old", updated_at=now - timedelta(days=200), messages=messages)
        _seed_hot_exchanges(storage, "old", "proj-1", messages)

        candidates = distillation_bridge.select_distillation_candidates(
            storage, age_threshold_days=180, now=now,
        )
        assert candidates == ["old"]

    def test_recent_conversation_is_excluded(self, storage: UnifiedStorage):
        now = datetime(2026, 1, 1)
        messages = _make_messages(1)
        _insert_conversation(storage, conversation_id="recent", updated_at=now - timedelta(days=5), messages=messages)
        _seed_hot_exchanges(storage, "recent", "proj-1", messages)

        candidates = distillation_bridge.select_distillation_candidates(
            storage, age_threshold_days=180, now=now,
        )
        assert candidates == []

    def test_already_evicted_conversation_is_excluded(self, storage: UnifiedStorage):
        """No exchange rows left (already distilled+evicted) drops out of
        candidacy on its own -- naturally idempotent, no palace state
        consulted."""
        now = datetime(2026, 1, 1)
        messages = _make_messages(1)
        _insert_conversation(storage, conversation_id="gone", updated_at=now - timedelta(days=400), messages=messages)
        # Note: no _seed_hot_exchanges call -- simulates post-eviction state.

        candidates = distillation_bridge.select_distillation_candidates(
            storage, age_threshold_days=180, now=now,
        )
        assert candidates == []

    def test_multiple_candidates_ordered_deterministically(self, storage: UnifiedStorage):
        now = datetime(2026, 1, 1)
        for conv_id in ("b-conv", "a-conv"):
            messages = _make_messages(1)
            _insert_conversation(storage, conversation_id=conv_id, updated_at=now - timedelta(days=365), messages=messages)
            _seed_hot_exchanges(storage, conv_id, "proj-1", messages)

        candidates = distillation_bridge.select_distillation_candidates(
            storage, age_threshold_days=30, now=now,
        )
        assert candidates == ["a-conv", "b-conv"]
