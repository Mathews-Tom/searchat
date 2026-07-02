"""Unit tests for UnifiedIndexer — DuckDB-native conversation indexer."""
from __future__ import annotations

import hashlib
from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock, patch

import numpy as np
import pytest

from searchat.config import Config
from searchat.core.unified_indexer import (
    UnifiedIndexer,
    _derive_exchange_id,
    _segment_exchanges,
)
from searchat.models import ConversationRecord, MessageRecord
from searchat.storage.schema import create_fts_indexes
from searchat.storage.unified_storage import UnifiedStorage


# ---------------------------------------------------------------------------
# Exchange ID generation
# ---------------------------------------------------------------------------

class TestDeriveExchangeId:
    def test_deterministic(self) -> None:
        id1 = _derive_exchange_id("conv-1", 0, 3)
        id2 = _derive_exchange_id("conv-1", 0, 3)
        assert id1 == id2

    def test_different_inputs_yield_different_ids(self) -> None:
        id1 = _derive_exchange_id("conv-1", 0, 3)
        id2 = _derive_exchange_id("conv-1", 0, 4)
        id3 = _derive_exchange_id("conv-2", 0, 3)
        assert id1 != id2
        assert id1 != id3

    def test_length_is_16_hex_chars(self) -> None:
        eid = _derive_exchange_id("abc", 1, 2)
        assert len(eid) == 16
        int(eid, 16)  # validates hex


# ---------------------------------------------------------------------------
# Exchange segmentation
# ---------------------------------------------------------------------------

class TestSegmentExchanges:
    def test_empty_messages(self) -> None:
        result = _segment_exchanges("c1", "p1", [], datetime.now())
        assert result == []

    def test_single_user_assistant_pair(self) -> None:
        msgs = [
            {"sequence": 0, "role": "user", "content": "Hello"},
            {"sequence": 1, "role": "assistant", "content": "Hi there"},
        ]
        exchanges = _segment_exchanges("c1", "p1", msgs, datetime(2025, 1, 1))
        assert len(exchanges) == 1
        exc = exchanges[0]
        assert exc["conversation_id"] == "c1"
        assert exc["project_id"] == "p1"
        assert exc["ply_start"] == 0
        assert exc["ply_end"] == 1
        assert "Hello" in exc["exchange_text"]
        assert "Hi there" in exc["exchange_text"]

    def test_multiple_exchanges(self) -> None:
        msgs = [
            {"sequence": 0, "role": "user", "content": "Q1"},
            {"sequence": 1, "role": "assistant", "content": "A1"},
            {"sequence": 2, "role": "user", "content": "Q2"},
            {"sequence": 3, "role": "assistant", "content": "A2"},
        ]
        exchanges = _segment_exchanges("c1", "p1", msgs, datetime(2025, 1, 1))
        assert len(exchanges) == 2
        assert exchanges[0]["ply_start"] == 0
        assert exchanges[0]["ply_end"] == 1
        assert exchanges[1]["ply_start"] == 2
        assert exchanges[1]["ply_end"] == 3

    def test_assistant_only_messages(self) -> None:
        msgs = [
            {"sequence": 0, "role": "assistant", "content": "I start the convo"},
        ]
        exchanges = _segment_exchanges("c1", "p1", msgs, datetime(2025, 1, 1))
        assert len(exchanges) == 1
        assert exchanges[0]["ply_start"] == 0
        assert exchanges[0]["ply_end"] == 0

    def test_user_without_response(self) -> None:
        msgs = [
            {"sequence": 0, "role": "user", "content": "Hello"},
        ]
        exchanges = _segment_exchanges("c1", "p1", msgs, datetime(2025, 1, 1))
        assert len(exchanges) == 1
        assert exchanges[0]["exchange_text"] == "Hello"

    def test_consecutive_assistant_messages(self) -> None:
        msgs = [
            {"sequence": 0, "role": "user", "content": "Q"},
            {"sequence": 1, "role": "assistant", "content": "Part 1"},
            {"sequence": 2, "role": "assistant", "content": "Part 2"},
        ]
        exchanges = _segment_exchanges("c1", "p1", msgs, datetime(2025, 1, 1))
        assert len(exchanges) == 1
        assert "Part 1" in exchanges[0]["exchange_text"]
        assert "Part 2" in exchanges[0]["exchange_text"]

    def test_exchange_ids_are_unique(self) -> None:
        msgs = [
            {"sequence": 0, "role": "user", "content": "Q1"},
            {"sequence": 1, "role": "assistant", "content": "A1"},
            {"sequence": 2, "role": "user", "content": "Q2"},
            {"sequence": 3, "role": "assistant", "content": "A2"},
        ]
        exchanges = _segment_exchanges("c1", "p1", msgs, datetime(2025, 1, 1))
        ids = [e["exchange_id"] for e in exchanges]
        assert len(ids) == len(set(ids))


# ---------------------------------------------------------------------------
# UnifiedIndexer safety guards
# ---------------------------------------------------------------------------

class TestUnifiedIndexerSafetyGuards:
    def test_index_all_raises_runtime_error(self, tmp_path: Path) -> None:
        storage = MagicMock()
        indexer = UnifiedIndexer(tmp_path, storage=storage)
        with pytest.raises(RuntimeError, match="Existing index detected"):
            indexer.index_all()

    def test_index_all_raises_even_with_force(self, tmp_path: Path) -> None:
        storage = MagicMock()
        indexer = UnifiedIndexer(tmp_path, storage=storage)
        with pytest.raises(RuntimeError, match="Existing index detected"):
            indexer.index_all(force=True)


# ---------------------------------------------------------------------------
# get_indexed_file_paths
# ---------------------------------------------------------------------------

class TestGetIndexedFilePaths:
    def test_returns_set_from_storage(self, tmp_path: Path) -> None:
        storage = MagicMock()
        cursor = MagicMock()
        cursor.execute.return_value.fetchall.return_value = [
            ("/path/a.jsonl",),
            ("/path/b.json",),
        ]
        storage._read_cursor.return_value = cursor

        indexer = UnifiedIndexer(tmp_path, storage=storage)
        paths = indexer.get_indexed_file_paths()

        assert paths == {"/path/a.jsonl", "/path/b.json"}

    def test_returns_empty_set_on_error(self, tmp_path: Path) -> None:
        storage = MagicMock()
        storage._read_cursor.side_effect = RuntimeError("no table")

        indexer = UnifiedIndexer(tmp_path, storage=storage)
        paths = indexer.get_indexed_file_paths()

        assert paths == set()


# ---------------------------------------------------------------------------
# index_append_only
# ---------------------------------------------------------------------------

class TestIndexAppendOnly:
    def test_skips_already_indexed_files(self, tmp_path: Path) -> None:
        storage = MagicMock()
        cursor = MagicMock()
        cursor.execute.return_value.fetchall.return_value = [
            ("/existing.jsonl",),
        ]
        storage._read_cursor.return_value = cursor

        indexer = UnifiedIndexer(tmp_path, storage=storage)
        stats = indexer.index_append_only(["/existing.jsonl"])

        assert stats.new_conversations == 0
        assert stats.skipped_conversations == 1

    def test_skips_nonexistent_files(self, tmp_path: Path) -> None:
        storage = MagicMock()
        cursor = MagicMock()
        cursor.execute.return_value.fetchall.return_value = []
        storage._read_cursor.return_value = cursor

        indexer = UnifiedIndexer(tmp_path, storage=storage)
        stats = indexer.index_append_only(["/nonexistent/file.jsonl"])

        assert stats.new_conversations == 0

    def test_raises_when_connectors_disabled(self, tmp_path: Path) -> None:
        storage = MagicMock()
        config = MagicMock()
        config.indexing.enable_connectors = False

        indexer = UnifiedIndexer(tmp_path, config, storage=storage)
        with pytest.raises(RuntimeError, match="Connector loading is disabled"):
            indexer.index_append_only(["/some/file.jsonl"])

    def test_indexes_new_file(self, tmp_path: Path) -> None:
        # Create a fake JSONL
        convo_file = tmp_path / "conv.jsonl"
        convo_file.write_text("")

        storage = MagicMock()
        cursor = MagicMock()
        cursor.execute.return_value.fetchall.return_value = []
        storage._read_cursor.return_value = cursor

        now = datetime.now()
        record = ConversationRecord(
            conversation_id="conv-1",
            project_id="proj-1",
            file_path=str(convo_file),
            title="Test Conversation",
            created_at=now,
            updated_at=now,
            message_count=2,
            messages=[
                MessageRecord(sequence=0, role="user", content="Hello", timestamp=now, has_code=False),
                MessageRecord(sequence=1, role="assistant", content="Hi", timestamp=now, has_code=False),
            ],
            full_text="Hello\nHi",
            embedding_id=0,
            file_hash="abc123",
            indexed_at=now,
        )

        fake_connector = MagicMock()
        fake_connector.name = "test"
        fake_connector.parse.return_value = record

        config = MagicMock()
        config.indexing.enable_connectors = True
        config.embedding.batch_size = 32
        config.expertise.enabled = False

        fake_embedder = MagicMock()
        fake_embedder.encode.return_value = [[0.1] * 384]

        indexer = UnifiedIndexer(tmp_path, config, storage=storage)

        with (
            patch("searchat.core.unified_indexer.detect_connector", return_value=fake_connector),
            patch.object(indexer, "_get_embedder", return_value=fake_embedder),
        ):
            stats = indexer.index_append_only([str(convo_file)])

        assert stats.new_conversations == 1
        assert stats.empty_conversations == 0
        storage.upsert_conversation.assert_called_once()
        storage.insert_messages.assert_called_once()
        storage.upsert_exchange.assert_called()
        storage.upsert_embedding.assert_called()
        storage.upsert_file_state.assert_called_once()

    def test_skips_empty_conversations(self, tmp_path: Path) -> None:
        convo_file = tmp_path / "empty.jsonl"
        convo_file.write_text("")

        storage = MagicMock()
        cursor = MagicMock()
        cursor.execute.return_value.fetchall.return_value = []
        storage._read_cursor.return_value = cursor

        now = datetime.now()
        record = ConversationRecord(
            conversation_id="conv-empty",
            project_id="proj-1",
            file_path=str(convo_file),
            title="Empty",
            created_at=now,
            updated_at=now,
            message_count=0,
            messages=[],
            full_text="",
            embedding_id=0,
            file_hash="def456",
            indexed_at=now,
        )

        fake_connector = MagicMock()
        fake_connector.name = "test"
        fake_connector.parse.return_value = record

        config = MagicMock()
        config.indexing.enable_connectors = True
        config.expertise.enabled = False

        indexer = UnifiedIndexer(tmp_path, config, storage=storage)

        with patch("searchat.core.unified_indexer.detect_connector", return_value=fake_connector):
            stats = indexer.index_append_only([str(convo_file)])

        assert stats.new_conversations == 0
        assert stats.empty_conversations == 1
        storage.upsert_conversation.assert_not_called()


# ---------------------------------------------------------------------------
# _record_messages_to_dicts
# ---------------------------------------------------------------------------

class TestRecordMessagesToDicts:
    def test_converts_messages(self) -> None:
        now = datetime.now()
        record = ConversationRecord(
            conversation_id="c",
            project_id="p",
            file_path="/x",
            title="T",
            created_at=now,
            updated_at=now,
            message_count=1,
            messages=[
                MessageRecord(
                    sequence=0,
                    role="user",
                    content="hello",
                    timestamp=now,
                    has_code=True,
                    code_blocks=["print('hi')"],
                ),
            ],
            full_text="hello",
            embedding_id=0,
            file_hash="h",
            indexed_at=now,
        )
        dicts = UnifiedIndexer._record_messages_to_dicts(record)
        assert len(dicts) == 1
        assert dicts[0]["role"] == "user"
        assert dicts[0]["content"] == "hello"
        assert dicts[0]["has_code"] is True
        assert dicts[0]["code_blocks"] == ["print('hi')"]


# ---------------------------------------------------------------------------
# rebuild_derived
# ---------------------------------------------------------------------------

class TestRebuildDerived:
    """rebuild_derived() rebuilds exchanges/embeddings/FTS/HNSW from persisted
    conversations/messages only — it must never touch source files."""

    @pytest.fixture()
    def real_storage(self, tmp_path: Path):
        db_path = tmp_path / "rebuild_derived.duckdb"
        storage = UnifiedStorage(db_path)
        yield storage
        storage.close()

    def _seed_conversation(
        self,
        storage: UnifiedStorage,
        conversation_id: str,
        *,
        project_id: str = "proj1",
        n_messages: int = 4,
        now: datetime | None = None,
    ) -> None:
        """Populate conversations/messages directly — never via a connector/file."""
        now = now or datetime(2026, 1, 1, 12, 0, 0)
        storage.upsert_conversation(
            conversation_id=conversation_id,
            project_id=project_id,
            file_path=f"/fake/does/not/exist/{conversation_id}.jsonl",
            title=f"Conversation {conversation_id}",
            created_at=now,
            updated_at=now,
            message_count=n_messages,
            full_text="hello world",
            file_hash=f"hash-{conversation_id}",
            indexed_at=now,
        )
        messages = [
            {
                "sequence": i,
                "role": "user" if i % 2 == 0 else "assistant",
                "content": f"{conversation_id} message {i} about sorting a python list",
                "timestamp": now,
                "has_code": False,
                "code_blocks": None,
            }
            for i in range(n_messages)
        ]
        storage.insert_messages(conversation_id, messages)

    def _deterministic_vector(self, text: str) -> list[float]:
        """Same text -> same 384-dim vector, every time."""
        seed = int(hashlib.sha256(text.encode()).hexdigest()[:8], 16)
        rng = np.random.default_rng(seed)
        return rng.random(384).tolist()

    def _make_deterministic_embedder(self) -> MagicMock:
        embedder = MagicMock()
        embedder.encode.side_effect = lambda batch, **kwargs: np.array(
            [self._deterministic_vector(text) for text in batch]
        )
        return embedder

    def test_zero_source_access_force_false(
        self, tmp_path: Path, real_storage: UnifiedStorage
    ) -> None:
        """force=False never calls a connector or discovers source files."""
        self._seed_conversation(real_storage, "conv-a")
        self._seed_conversation(real_storage, "conv-b")

        config = Config.load()
        indexer = UnifiedIndexer(tmp_path, config, storage=real_storage)
        embedder = self._make_deterministic_embedder()

        with (
            patch(
                "searchat.core.unified_indexer.detect_connector",
                side_effect=AssertionError("must never touch source files"),
            ),
            patch(
                "searchat.core.unified_indexer.discover_all_files",
                side_effect=AssertionError("must never touch source files"),
            ),
            patch.object(indexer, "_get_embedder", return_value=embedder),
        ):
            stats = indexer.rebuild_derived(force=False)

        assert stats.conversations_processed == 2
        assert stats.exchanges_rebuilt == 4
        assert stats.embeddings_rebuilt == 4
        assert stats.forced is False
        assert real_storage.get_exchange_count() == 4
        assert real_storage.get_embedding_count() == 4

    def test_zero_source_access_force_true_rebuilds_indexes(
        self, tmp_path: Path, real_storage: UnifiedStorage
    ) -> None:
        """force=True also never touches source files, and rebuilds FTS + HNSW."""
        self._seed_conversation(real_storage, "conv-a")
        self._seed_conversation(real_storage, "conv-b")

        config = Config.load()
        indexer = UnifiedIndexer(tmp_path, config, storage=real_storage)
        embedder = self._make_deterministic_embedder()

        with (
            patch(
                "searchat.core.unified_indexer.detect_connector",
                side_effect=AssertionError("must never touch source files"),
            ),
            patch(
                "searchat.core.unified_indexer.discover_all_files",
                side_effect=AssertionError("must never touch source files"),
            ),
            patch.object(indexer, "_get_embedder", return_value=embedder),
        ):
            stats = indexer.rebuild_derived(force=True)

        assert stats.forced is True
        assert stats.conversations_processed == 2
        assert stats.exchanges_rebuilt == 4
        assert stats.embeddings_rebuilt == 4

        bm25_rows = real_storage.connection.execute(
            "SELECT exchange_id, fts_main_exchanges.match_bm25(exchange_id, 'sorting') AS score "
            "FROM exchanges WHERE score IS NOT NULL ORDER BY score DESC"
        ).fetchall()
        assert len(bm25_rows) > 0

        hnsw_rows = real_storage.connection.execute(
            "SELECT index_name FROM duckdb_indexes() WHERE index_name = 'verbatim_hnsw'"
        ).fetchall()
        assert hnsw_rows == [("verbatim_hnsw",)]

    def test_incremental_leaves_populated_conversations_untouched(
        self, tmp_path: Path, real_storage: UnifiedStorage
    ) -> None:
        """force=False only (re)segments conversations with zero exchange rows."""
        self._seed_conversation(real_storage, "conv-a")

        config = Config.load()
        indexer = UnifiedIndexer(tmp_path, config, storage=real_storage)
        embedder = self._make_deterministic_embedder()

        with patch.object(indexer, "_get_embedder", return_value=embedder):
            first_stats = indexer.rebuild_derived(force=False)

        assert first_stats.conversations_processed == 1
        exchange_ids_before = {
            row[0]
            for row in real_storage.connection.execute(
                "SELECT exchange_id FROM exchanges"
            ).fetchall()
        }
        assert exchange_ids_before

        # conv-b has messages but zero exchanges yet; conv-a is already populated.
        self._seed_conversation(real_storage, "conv-b")

        with patch.object(indexer, "_get_embedder", return_value=embedder):
            second_stats = indexer.rebuild_derived(force=False)

        assert second_stats.conversations_processed == 1
        exchange_ids_after = {
            row[0]
            for row in real_storage.connection.execute(
                "SELECT exchange_id FROM exchanges"
            ).fetchall()
        }
        # conv-a's exchanges are untouched by the second pass.
        assert exchange_ids_before <= exchange_ids_after
        # conv-b's exchanges were newly added.
        assert exchange_ids_after - exchange_ids_before

    def test_determinism_matches_from_scratch_ingestion(
        self, tmp_path: Path, real_storage: UnifiedStorage
    ) -> None:
        """rebuild_derived(force=True) reproduces bit-identical search results."""
        convo_file = tmp_path / "conv.jsonl"
        convo_file.write_text("")

        now = datetime(2026, 1, 1, 12, 0, 0)
        messages = [
            MessageRecord(sequence=0, role="user", content="how do I sort a list in python", timestamp=now, has_code=False),
            MessageRecord(sequence=1, role="assistant", content="use sorted() or list.sort()", timestamp=now, has_code=False),
            MessageRecord(sequence=2, role="user", content="what about reverse sorting", timestamp=now, has_code=False),
            MessageRecord(sequence=3, role="assistant", content="pass reverse=True to sorted()", timestamp=now, has_code=False),
        ]
        record = ConversationRecord(
            conversation_id="conv-det",
            project_id="proj-det",
            file_path=str(convo_file),
            title="Determinism Test",
            created_at=now,
            updated_at=now,
            message_count=len(messages),
            messages=messages,
            full_text="\n".join(m.content for m in messages),
            embedding_id=0,
            file_hash="det-hash",
            indexed_at=now,
        )

        fake_connector = MagicMock()
        fake_connector.name = "test"
        fake_connector.parse.return_value = record

        config = Config.load()
        config.expertise.enabled = False
        indexer = UnifiedIndexer(tmp_path, config, storage=real_storage)
        embedder = self._make_deterministic_embedder()

        with (
            patch("searchat.core.unified_indexer.detect_connector", return_value=fake_connector),
            patch.object(indexer, "_get_embedder", return_value=embedder),
        ):
            indexer.index_append_only([str(convo_file)])

        # index_append_only() does not build the FTS index (only rebuild_derived
        # does); build it once here so both passes are compared on equal footing.
        create_fts_indexes(real_storage.connection)

        query = "sort"
        first_bm25 = real_storage.connection.execute(
            "SELECT exchange_id, fts_main_exchanges.match_bm25(exchange_id, ?) AS score "
            "FROM exchanges WHERE score IS NOT NULL ORDER BY score DESC, exchange_id",
            [query],
        ).fetchall()
        assert first_bm25

        probe_row = real_storage.connection.execute(
            "SELECT exchange_id, embedding FROM verbatim_embeddings ORDER BY exchange_id LIMIT 1"
        ).fetchone()
        assert probe_row is not None
        probe_vec = probe_row[1]

        first_neighbors = real_storage.connection.execute(
            "SELECT exchange_id, array_cosine_distance(embedding, ?::FLOAT[384]) AS dist "
            "FROM verbatim_embeddings ORDER BY dist, exchange_id",
            [probe_vec],
        ).fetchall()
        assert first_neighbors

        # Wipe derived data and rebuild from the SAME persisted messages.
        real_storage.clear_exchanges()
        real_storage.clear_embeddings()
        real_storage.drop_hnsw_index()

        with patch.object(indexer, "_get_embedder", return_value=embedder):
            indexer.rebuild_derived(force=True)

        second_bm25 = real_storage.connection.execute(
            "SELECT exchange_id, fts_main_exchanges.match_bm25(exchange_id, ?) AS score "
            "FROM exchanges WHERE score IS NOT NULL ORDER BY score DESC, exchange_id",
            [query],
        ).fetchall()
        second_neighbors = real_storage.connection.execute(
            "SELECT exchange_id, array_cosine_distance(embedding, ?::FLOAT[384]) AS dist "
            "FROM verbatim_embeddings ORDER BY dist, exchange_id",
            [probe_vec],
        ).fetchall()

        assert second_bm25 == first_bm25
        assert second_neighbors == first_neighbors

    def test_rebuild_stats_fields(
        self, tmp_path: Path, real_storage: UnifiedStorage
    ) -> None:
        """RebuildStats fields accurately reflect the force=False and force=True runs."""
        self._seed_conversation(real_storage, "conv-a")

        config = Config.load()
        indexer = UnifiedIndexer(tmp_path, config, storage=real_storage)
        embedder = self._make_deterministic_embedder()

        with patch.object(indexer, "_get_embedder", return_value=embedder):
            not_forced = indexer.rebuild_derived(force=False)

        assert not_forced.conversations_processed == 1
        assert not_forced.exchanges_rebuilt == 2
        assert not_forced.embeddings_rebuilt == 2
        assert not_forced.forced is False
        assert not_forced.rebuild_time_seconds >= 0

        with patch.object(indexer, "_get_embedder", return_value=embedder):
            forced = indexer.rebuild_derived(force=True)

        assert forced.conversations_processed == 1
        assert forced.exchanges_rebuilt == 2
        assert forced.embeddings_rebuilt == 2
        assert forced.forced is True
        assert forced.rebuild_time_seconds >= 0
