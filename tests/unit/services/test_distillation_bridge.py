"""Unit tests for `searchat.services.distillation_bridge` (M9).

Coverage map:
- `TestSelectDistillationCandidates` -- age-based candidate selection,
  palace-independent.
- `TestGenerateDistillate` -- distillate generation via the palace
  `Distiller`, adapted onto `UnifiedStorage`.
- `TestGracefulDegradation` -- the `palace` extra (faiss-cpu) missing
  degrades to a disabled feature, never a crash.
- `TestEvictHotRows` -- hot-index eviction never touches
  `conversations`/`messages`.
- `TestRehydrateVerbatim` -- lossless promotion round trip.
- `TestRunTieringCycle` -- the end-to-end orchestrator.
- `TestBenchmarkAcceptance` -- the M9 fixture-benchmark acceptance
  criteria: recall@10 and index-size reduction.
"""
from __future__ import annotations

import sys
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path

import pytest

from searchat.config import Config
from searchat.core.progress import NullProgressAdapter
from searchat.core.unified_indexer import UnifiedIndexer, _segment_exchanges
from searchat.palace.llm import DistillationLLM, DistillationOutput
from searchat.palace.storage import PalaceStorage
from searchat.services import distillation_bridge
from searchat.storage.unified_storage import UnifiedStorage

from tests.fixtures.distillation_benchmark import (
    MAX_RELATIVE_RECALL_DROP,
    MIN_INDEX_SIZE_REDUCTION_FACTOR,
    build_fixture_corpus,
    build_query_set,
    distillate_embedding,
    recall_at_k,
)

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

    def test_retention_never_touch_project_excluded_even_when_older_than_global_threshold(
        self, storage: UnifiedStorage
    ) -> None:
        """M12: a conversation whose project resolves to never_touch is
        excluded outright, even though it is far older than
        age_threshold_days -- a sibling conversation in a different
        project is still selected, proving the exclusion is
        project-specific, not a side effect of passing `retention`."""
        from searchat.config.settings import RetentionConfig

        now = datetime(2026, 1, 1)
        never_touch_messages = _make_messages(1)
        _insert_conversation(
            storage,
            conversation_id="never-touch-conv",
            project_id="proj-never-touch",
            updated_at=now - timedelta(days=400),
            messages=never_touch_messages,
        )
        _seed_hot_exchanges(storage, "never-touch-conv", "proj-never-touch", never_touch_messages)

        other_messages = _make_messages(1)
        _insert_conversation(
            storage,
            conversation_id="other-conv",
            project_id="proj-1",
            updated_at=now - timedelta(days=400),
            messages=other_messages,
        )
        _seed_hot_exchanges(storage, "other-conv", "proj-1", other_messages)

        retention = RetentionConfig.from_dict(
            {"project": {"proj-never-touch": {"never_touch": True}}}
        )
        candidates = distillation_bridge.select_distillation_candidates(
            storage, age_threshold_days=180, now=now, retention=retention,
        )
        assert candidates == ["other-conv"]



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

    def test_run_tiering_cycle_reports_unavailable_when_palace_disabled_in_config(
        self, storage: UnifiedStorage, config: Config, tmp_path: Path
    ):
        now = datetime(2026, 1, 1)
        messages = _make_messages(1)
        _insert_conversation(storage, conversation_id="old", updated_at=now - timedelta(days=400), messages=messages)
        _seed_hot_exchanges(storage, "old", "proj-1", messages)
        config.palace.enabled = False

        stats = distillation_bridge.run_tiering_cycle(
            storage, config=config, llm=_FakeDistillationLLM(), search_dir=tmp_path, now=now,
        )

        assert stats.candidates_considered == 1
        assert stats.palace_unavailable is True
        assert stats.conversations_evicted == 0
        # Verbatim rows must survive untouched when the feature is disabled.
        assert storage.get_row_counts()["exchanges"] == 1

    def test_run_tiering_cycle_reports_unavailable_when_extra_missing(
        self, monkeypatch, storage: UnifiedStorage, config: Config, tmp_path: Path
    ):
        now = datetime(2026, 1, 1)
        messages = _make_messages(1)
        _insert_conversation(storage, conversation_id="old", updated_at=now - timedelta(days=400), messages=messages)
        _seed_hot_exchanges(storage, "old", "proj-1", messages)
        config.palace.enabled = True
        monkeypatch.setattr(distillation_bridge, "palace_available", lambda: False)

        stats = distillation_bridge.run_tiering_cycle(
            storage, config=config, llm=_FakeDistillationLLM(), search_dir=tmp_path, now=now,
        )

        assert stats.palace_unavailable is True
        assert stats.conversations_evicted == 0


# ---------------------------------------------------------------------------
# 4. Hot-index eviction
# ---------------------------------------------------------------------------


class TestEvictHotRows:
    def test_evicts_exchanges_and_embeddings_for_target_conversation_only(self, storage: UnifiedStorage):
        messages_a = _make_messages(2)
        messages_b = _make_messages(1)
        _insert_conversation(storage, conversation_id="a", updated_at=datetime(2025, 1, 1), messages=messages_a)
        _insert_conversation(storage, conversation_id="b", updated_at=datetime(2025, 1, 1), messages=messages_b)
        _seed_hot_exchanges(storage, "a", "proj-1", messages_a)
        _seed_hot_exchanges(storage, "b", "proj-1", messages_b)

        result = distillation_bridge.evict_hot_rows(storage, "a")

        assert result.exchanges_evicted == 2
        assert result.embeddings_evicted == 2

        cur = storage.connection.cursor()
        remaining_a = cur.execute("SELECT count(*) FROM exchanges WHERE conversation_id = 'a'").fetchone()[0]
        remaining_b = cur.execute("SELECT count(*) FROM exchanges WHERE conversation_id = 'b'").fetchone()[0]
        cur.close()
        assert remaining_a == 0
        assert remaining_b == 1

    def test_never_touches_conversations_or_messages_tables(self, storage: UnifiedStorage):
        messages = _make_messages(3)
        _insert_conversation(storage, conversation_id="a", updated_at=datetime(2025, 1, 1), messages=messages)
        _seed_hot_exchanges(storage, "a", "proj-1", messages)

        before_conv = storage.get_conversation_meta("a")
        before_counts = storage.get_row_counts()

        distillation_bridge.evict_hot_rows(storage, "a")

        after_conv = storage.get_conversation_meta("a")
        after_counts = storage.get_row_counts()

        assert after_conv == before_conv
        assert after_counts["conversations"] == before_counts["conversations"]
        assert after_counts["messages"] == before_counts["messages"]
        assert after_counts["exchanges"] == 0
        assert after_counts["verbatim_embeddings"] == 0

    def test_eviction_on_conversation_with_no_hot_rows_is_a_safe_no_op(self, storage: UnifiedStorage):
        result = distillation_bridge.evict_hot_rows(storage, "does-not-exist")
        assert result.exchanges_evicted == 0
        assert result.embeddings_evicted == 0


# ---------------------------------------------------------------------------
# 5. Promotion path (rehydrate_verbatim)
# ---------------------------------------------------------------------------


class TestRehydrateVerbatim:
    def _snapshot_exchanges(self, storage: UnifiedStorage, conversation_id: str) -> list[tuple]:
        cur = storage.connection.cursor()
        try:
            return cur.execute(
                "SELECT exchange_id, conversation_id, project_id, ply_start, ply_end, "
                "exchange_text, created_at FROM exchanges WHERE conversation_id = ? "
                "ORDER BY exchange_id",
                [conversation_id],
            ).fetchall()
        finally:
            cur.close()

    def _snapshot_embeddings(self, storage: UnifiedStorage, conversation_id: str) -> list[tuple]:
        cur = storage.connection.cursor()
        try:
            return cur.execute(
                "SELECT ve.exchange_id, ve.embedding FROM verbatim_embeddings ve "
                "JOIN exchanges e ON e.exchange_id = ve.exchange_id "
                "WHERE e.conversation_id = ? ORDER BY ve.exchange_id",
                [conversation_id],
            ).fetchall()
        finally:
            cur.close()

    def test_round_trip_reproduces_original_rows_exactly(self, storage: UnifiedStorage, config: Config):
        conversation_id = "conv-1"
        project_id = "proj-1"
        messages = _make_messages(3)
        _insert_conversation(storage, conversation_id=conversation_id, project_id=project_id, updated_at=datetime(2025, 1, 1), messages=messages)

        # Build the original hot index via the exact same machinery
        # rehydrate_verbatim reuses, so pre/post are directly comparable.
        exchanges = _segment_exchanges(conversation_id, project_id, messages, messages[0]["timestamp"])
        for exc in exchanges:
            storage.upsert_exchange(**exc)
        indexer = UnifiedIndexer(search_dir=Path("."), config=config, storage=storage)
        indexer._embed_exchanges(exchanges, NullProgressAdapter())

        original_exchanges = self._snapshot_exchanges(storage, conversation_id)
        original_embeddings = self._snapshot_embeddings(storage, conversation_id)
        assert len(original_exchanges) == 3

        eviction = distillation_bridge.evict_hot_rows(storage, conversation_id)
        assert eviction.exchanges_evicted == 3
        assert self._snapshot_exchanges(storage, conversation_id) == []

        result = distillation_bridge.rehydrate_verbatim(storage, conversation_id, config=config)

        assert result.exchanges_restored == 3
        assert result.embeddings_restored == 3
        assert self._snapshot_exchanges(storage, conversation_id) == original_exchanges
        assert self._snapshot_embeddings(storage, conversation_id) == original_embeddings

    def test_raises_key_error_when_conversation_has_no_messages(self, storage: UnifiedStorage, config: Config):
        with pytest.raises(KeyError):
            distillation_bridge.rehydrate_verbatim(storage, "missing", config=config)

# ---------------------------------------------------------------------------
# 6. End-to-end orchestrator
# ---------------------------------------------------------------------------


class TestRunTieringCycle:
    def test_distills_and_evicts_old_conversations_leaving_recent_ones_hot(
        self, storage: UnifiedStorage, config: Config, tmp_path: Path
    ):
        now = datetime(2026, 1, 1)
        old_messages = _make_messages(2)
        recent_messages = _make_messages(2)
        _insert_conversation(storage, conversation_id="old", updated_at=now - timedelta(days=400), messages=old_messages)
        _insert_conversation(storage, conversation_id="recent", updated_at=now - timedelta(days=5), messages=recent_messages)
        _seed_hot_exchanges(storage, "old", "proj-1", old_messages)
        _seed_hot_exchanges(storage, "recent", "proj-1", recent_messages)
        config.palace.enabled = True

        stats = distillation_bridge.run_tiering_cycle(
            storage,
            config=config,
            llm=_FakeDistillationLLM(),
            search_dir=tmp_path,
            embedder=_FixedEmbedder(),
            now=now,
        )

        assert stats.palace_unavailable is False
        assert stats.candidates_considered == 1
        assert stats.conversations_distilled == 1
        assert stats.conversations_evicted == 1
        assert stats.exchanges_evicted == 2

        counts = storage.get_row_counts()
        cur = storage.connection.cursor()
        old_hot = cur.execute("SELECT count(*) FROM exchanges WHERE conversation_id = 'old'").fetchone()[0]
        recent_hot = cur.execute("SELECT count(*) FROM exchanges WHERE conversation_id = 'recent'").fetchone()[0]
        cur.close()
        assert old_hot == 0
        assert recent_hot == 2
        assert counts["conversations"] == 2
        assert counts["messages"] == len(old_messages) + len(recent_messages)

    def test_skips_eviction_for_conversations_with_no_valid_exchanges(
        self, storage: UnifiedStorage, config: Config, tmp_path: Path
    ):
        now = datetime(2026, 1, 1)
        tiny_messages = [
            {"sequence": 0, "role": "user", "content": "hi", "timestamp": now, "has_code": False, "code_blocks": None},
            {"sequence": 1, "role": "assistant", "content": "hey", "timestamp": now, "has_code": False, "code_blocks": None},
        ]
        _insert_conversation(storage, conversation_id="tiny", updated_at=now - timedelta(days=400), messages=tiny_messages)
        _seed_hot_exchanges(storage, "tiny", "proj-1", tiny_messages)
        config.palace.enabled = True

        stats = distillation_bridge.run_tiering_cycle(
            storage, config=config, llm=_NoValidExchangesLLM(), search_dir=tmp_path,
            embedder=_FixedEmbedder(), now=now,
        )

        assert stats.candidates_considered == 1
        assert stats.conversations_distilled == 0
        assert stats.conversations_evicted == 0
        assert storage.get_row_counts()["exchanges"] == 1


# ---------------------------------------------------------------------------
# 7. M9 fixture-benchmark acceptance criteria
# ---------------------------------------------------------------------------


class _TopicAwareFakeLLM(DistillationLLM):
    """Embeds the conversation_id into the distillate text so the paired
    fake embedder can look up this benchmark's precomputed distillate
    vector for that conversation -- lets the test control distillate
    embedding geometry precisely without a real LLM or embedding model."""

    def distill(self, inputs):
        return [
            DistillationOutput(
                exchange_core=f"conv={i.conversation_id}",
                specific_context="distilled",
                room_assignments=[],
            )
            for i in inputs
        ]


class _TopicAwareFakeEmbedder:
    def __init__(self, topic_by_conversation: dict[str, str]) -> None:
        self._topic_by_conversation = topic_by_conversation

    def encode(self, texts, batch_size=32):
        import numpy as np

        vectors = []
        for text in texts:
            conversation_id = text.split("\n", 1)[0].removeprefix("conv=")
            topic = self._topic_by_conversation[conversation_id]
            vectors.append(distillate_embedding(topic, conversation_id))
        return np.array(vectors, dtype=np.float32)


@dataclass
class _BenchmarkRun:
    corpus: list
    queries: list
    pre_row_count: int
    post_row_count: int
    pre_embedding_by_conversation: dict
    post_embedding_by_conversation: dict
    still_hot: set
    stats: object


def _run_benchmark(storage: UnifiedStorage, config: Config, tmp_path: Path) -> _BenchmarkRun:
    """Seeds the fixture corpus into a real UnifiedStorage, runs the real
    M9 tiering pipeline (distillation_bridge.run_tiering_cycle through the
    real Distiller/PalaceStorage, with a topic-aware fake LLM/embedder
    controlling distillate geometry precisely), and returns everything
    both acceptance tests need."""
    base_date = datetime(2026, 7, 1)
    corpus = build_fixture_corpus(base_date=base_date)
    queries = build_query_set(corpus)
    topic_by_conversation = {c.conversation_id: c.topic for c in corpus}

    for conversation in corpus:
        messages = []
        seq = 0
        for exchange in conversation.exchanges:
            messages.append({
                "sequence": seq, "role": "user",
                "content": f"Tell me about {exchange.text}", "timestamp": conversation.updated_at,
                "has_code": False, "code_blocks": None,
            })
            seq += 1
            messages.append({
                "sequence": seq, "role": "assistant",
                "content": f"{exchange.text}. " * 3, "timestamp": conversation.updated_at,
                "has_code": False, "code_blocks": None,
            })
            seq += 1
        _insert_conversation(
            storage, conversation_id=conversation.conversation_id,
            project_id=conversation.project_id, updated_at=conversation.updated_at,
            messages=messages,
        )
        segmented = _segment_exchanges(
            conversation.conversation_id, conversation.project_id, messages, conversation.updated_at,
        )
        assert len(segmented) == len(conversation.exchanges)
        for exc_row, fixture_exchange in zip(segmented, conversation.exchanges):
            storage.upsert_exchange(**exc_row)
            storage.upsert_embedding(exc_row["exchange_id"], fixture_exchange.verbatim_embedding)

    pre_row_count = storage.get_row_counts()["verbatim_embeddings"]
    pre_embedding_by_conversation = {
        c.conversation_id: c.exchanges[0].verbatim_embedding for c in corpus
    }

    config.palace.enabled = True
    config.distillation.age_threshold_days = 45
    stats = distillation_bridge.run_tiering_cycle(
        storage,
        config=config,
        llm=_TopicAwareFakeLLM(),
        search_dir=tmp_path,
        embedder=_TopicAwareFakeEmbedder(topic_by_conversation),
        now=base_date,
    )

    post_row_count = storage.get_row_counts()["verbatim_embeddings"]
    cur = storage.connection.cursor()
    still_hot = {
        row[0]
        for row in cur.execute("SELECT DISTINCT conversation_id FROM exchanges").fetchall()
    }
    cur.close()

    post_embedding_by_conversation: dict[str, list[float]] = {}
    for c in corpus:
        if c.conversation_id in still_hot:
            post_embedding_by_conversation[c.conversation_id] = c.exchanges[0].verbatim_embedding
        else:
            post_embedding_by_conversation[c.conversation_id] = distillate_embedding(
                c.topic, c.conversation_id,
            )

    return _BenchmarkRun(
        corpus=corpus,
        queries=queries,
        pre_row_count=pre_row_count,
        post_row_count=post_row_count,
        pre_embedding_by_conversation=pre_embedding_by_conversation,
        post_embedding_by_conversation=post_embedding_by_conversation,
        still_hot=still_hot,
        stats=stats,
    )


class TestBenchmarkAcceptance:
    """Exercises the real `distillation_bridge` -> `Distiller` ->
    `PalaceStorage` pipeline against the fixture corpus, then measures
    recall@10 and index-size reduction per M9's acceptance criteria."""

    def test_recall_at_10_meets_m9_acceptance_budget(
        self, storage: UnifiedStorage, config: Config, tmp_path: Path
    ):
        run = _run_benchmark(storage, config, tmp_path)

        pre_recall = recall_at_k(run.queries, run.pre_embedding_by_conversation, k=10)
        assert pre_recall >= 0.99  # sanity: fixture geometry is well-separated

        distilled_queries = [
            q for q in run.queries if not (q.relevant_conversation_ids & run.still_hot)
        ]
        assert distilled_queries, "fixture must actually exercise the distilled path"

        pre_recall_distilled = recall_at_k(distilled_queries, run.pre_embedding_by_conversation, k=10)
        post_recall_distilled = recall_at_k(distilled_queries, run.post_embedding_by_conversation, k=10)

        assert pre_recall_distilled > 0
        relative_drop = (pre_recall_distilled - post_recall_distilled) / pre_recall_distilled
        assert relative_drop <= MAX_RELATIVE_RECALL_DROP, (
            f"distilled-conversation recall@10 dropped {relative_drop:.1%}, "
            f"exceeding the {MAX_RELATIVE_RECALL_DROP:.0%} budget "
            f"(pre={pre_recall_distilled:.3f}, post={post_recall_distilled:.3f})"
        )

    def test_index_size_reduction_meets_m9_acceptance_budget(
        self, storage: UnifiedStorage, config: Config, tmp_path: Path
    ):
        run = _run_benchmark(storage, config, tmp_path)

        assert run.pre_row_count == sum(len(c.exchanges) for c in run.corpus)
        reduction_factor = run.pre_row_count / run.post_row_count
        assert reduction_factor >= MIN_INDEX_SIZE_REDUCTION_FACTOR, (
            f"expected >= {MIN_INDEX_SIZE_REDUCTION_FACTOR}x reduction, got {reduction_factor:.2f}x "
            f"(pre={run.pre_row_count}, post={run.post_row_count})"
        )