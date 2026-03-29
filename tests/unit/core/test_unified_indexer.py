"""Unit tests for UnifiedIndexer — DuckDB-native conversation indexer."""
from __future__ import annotations

from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from searchat.core.unified_indexer import (
    UnifiedIndexer,
    _derive_exchange_id,
    _segment_exchanges,
)
from searchat.models import ConversationRecord, MessageRecord


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
