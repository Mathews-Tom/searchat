"""Unit tests for `searchat.services.distillation_bridge` (M9).

Coverage map:
- `TestSelectDistillationCandidates` -- age-based candidate selection,
  palace-independent.
- `TestGenerateDistillate` -- distillate generation via the palace
  `Distiller`, adapted onto `UnifiedStorage`.
- `TestGracefulDegradation` -- the `palace` extra (faiss-cpu) missing
  degrades to a disabled feature, never a crash.

Later commits/PRs in this stack add hot-index eviction, the promotion
path, the end-to-end orchestrator, and the fixture-benchmark acceptance
tests.
"""
from __future__ import annotations

import sys
from datetime import datetime, timedelta
from pathlib import Path

import pytest

from searchat.config import Config
from searchat.core.unified_indexer import _segment_exchanges
from searchat.palace.llm import DistillationLLM, DistillationOutput
from searchat.palace.storage import PalaceStorage
from searchat.services import distillation_bridge
from searchat.storage.unified_storage import UnifiedStorage

# ---------------------------------------------------------------------------
# Shared fixtures / helpers
# ---------------------------------------------------------------------------


@pytest.fixture()
def storage(tmp_path: Path):
    s = UnifiedStorage(tmp_path / "unified.duckdb")
    yield s
    s.close()


@pytest.fixture()
def config() -> Config:
    return Config.load()


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


class _FakeDistillationLLM(DistillationLLM):
    """Deterministic stand-in: never shells out, one output per input."""

    def distill(self, inputs):
        return [
            DistillationOutput(
                exchange_core=f"core:{i.conversation_id}:{i.ply_start}-{i.ply_end}",
                specific_context="ctx",
                room_assignments=[],
            )
            for i in inputs
        ]


class _NoValidExchangesLLM(DistillationLLM):
    """Never actually invoked when there are no valid exchanges to distill,
    but must exist to satisfy the `Distiller` constructor's type."""

    def distill(self, inputs):
        raise AssertionError("distill() should not be called with zero valid exchanges")


class _FixedEmbedder:
    def encode(self, texts, batch_size=32):
        import numpy as np

        return np.array([[0.2] * 384 for _ in texts], dtype=np.float32)


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


# ---------------------------------------------------------------------------
# 2. Distillate generation
# ---------------------------------------------------------------------------


class TestGenerateDistillate:
    def test_generates_and_persists_a_distillate(self, storage: UnifiedStorage, config: Config, tmp_path: Path):
        messages = _make_messages(2)
        _insert_conversation(storage, conversation_id="conv-1", project_id="proj-x", updated_at=datetime(2025, 1, 1), messages=messages)

        palace_storage = PalaceStorage(tmp_path / "data")
        try:
            result = distillation_bridge.generate_distillate(
                storage,
                conversation_id="conv-1",
                config=config,
                llm=_FakeDistillationLLM(),
                search_dir=tmp_path,
                embedder=_FixedEmbedder(),
                palace_storage=palace_storage,
            )

            assert result.conversation_id == "conv-1"
            assert result.objects_created == 2
            assert result.has_distillate is True

            objects = palace_storage.get_all_objects(project_id="proj-x")
            assert {o.conversation_id for o in objects} == {"conv-1"}
            assert all(o.distilled_text.startswith("core:conv-1:") for o in objects)
        finally:
            palace_storage.close()

    def test_no_valid_exchanges_yields_no_distillate(self, storage: UnifiedStorage, config: Config, tmp_path: Path):
        """Messages too short to clear Distiller's own min_exchange_chars
        filter -- `has_distillate` must be False so callers know not to
        evict (nothing to fall back on)."""
        tiny_messages = [
            {"sequence": 0, "role": "user", "content": "hi", "timestamp": datetime(2025, 1, 1), "has_code": False, "code_blocks": None},
            {"sequence": 1, "role": "assistant", "content": "hey", "timestamp": datetime(2025, 1, 1), "has_code": False, "code_blocks": None},
        ]
        _insert_conversation(storage, conversation_id="tiny", updated_at=datetime(2025, 1, 1), messages=tiny_messages)

        palace_storage = PalaceStorage(tmp_path / "data")
        try:
            result = distillation_bridge.generate_distillate(
                storage,
                conversation_id="tiny",
                config=config,
                llm=_NoValidExchangesLLM(),
                search_dir=tmp_path,
                embedder=_FixedEmbedder(),
                palace_storage=palace_storage,
            )
            assert result.objects_created == 0
            assert result.has_distillate is False
        finally:
            palace_storage.close()

    def test_idempotent_second_call_reports_has_distillate_without_new_objects(
        self, storage: UnifiedStorage, config: Config, tmp_path: Path
    ):
        messages = _make_messages(1)
        _insert_conversation(storage, conversation_id="conv-1", updated_at=datetime(2025, 1, 1), messages=messages)

        palace_storage = PalaceStorage(tmp_path / "data")
        try:
            first = distillation_bridge.generate_distillate(
                storage, conversation_id="conv-1", config=config, llm=_FakeDistillationLLM(),
                search_dir=tmp_path, embedder=_FixedEmbedder(), palace_storage=palace_storage,
            )
            second = distillation_bridge.generate_distillate(
                storage, conversation_id="conv-1", config=config, llm=_FakeDistillationLLM(),
                search_dir=tmp_path, embedder=_FixedEmbedder(), palace_storage=palace_storage,
            )
            assert first.objects_created == 1
            assert second.objects_created == 0
            assert second.has_distillate is True
        finally:
            palace_storage.close()



# ---------------------------------------------------------------------------
# 3. Graceful degradation
# ---------------------------------------------------------------------------


class TestGracefulDegradation:
    def test_palace_available_reflects_importability(self):
        # Whatever the real environment, this must not raise.
        assert isinstance(distillation_bridge.palace_available(), bool)

    def test_generate_distillate_raises_palace_unavailable_not_import_error(
        self, monkeypatch, storage: UnifiedStorage, config: Config, tmp_path: Path
    ):
        monkeypatch.setitem(sys.modules, "searchat.palace.distiller", None)

        with pytest.raises(distillation_bridge.PalaceUnavailableError):
            distillation_bridge.generate_distillate(
                storage,
                conversation_id="conv-1",
                config=config,
                llm=_FakeDistillationLLM(),
                search_dir=tmp_path,
            )