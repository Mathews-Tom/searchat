"""Tests for DuckDB-backed UnifiedStorage."""
from __future__ import annotations

from datetime import datetime

import pytest

from searchat.storage.schema import EMBEDDING_DIM, ensure_tables
from searchat.storage.unified_storage import UnifiedStorage


@pytest.fixture()
def storage(tmp_path):
    """Create an in-memory-like UnifiedStorage for testing."""
    db_path = tmp_path / "test.duckdb"
    s = UnifiedStorage(db_path)
    yield s
    s.close()


# -- Schema --

class TestSchema:
    def test_ensure_tables_creates_all_tables(self, storage):
        counts = storage.get_row_counts()
        assert set(counts.keys()) == {
            "conversations", "messages", "exchanges",
            "verbatim_embeddings", "source_file_state", "code_blocks",
        }
        assert all(v == 0 for v in counts.values())

    def test_ensure_tables_idempotent(self, storage):
        ensure_tables(storage.connection)
        counts = storage.get_row_counts()
        assert all(v == 0 for v in counts.values())


# -- Conversation CRUD --

class TestConversationCRUD:
    def _sample_conversation(self, **overrides):
        defaults = {
            "conversation_id": "conv-001",
            "project_id": "proj-alpha",
            "file_path": "/data/conv.jsonl",
            "title": "Test Conversation",
            "created_at": datetime(2026, 1, 1),
            "updated_at": datetime(2026, 1, 2),
            "message_count": 5,
            "full_text": "Hello world",
            "file_hash": "abc123",
            "indexed_at": datetime(2026, 1, 3),
        }
        defaults.update(overrides)
        return defaults

    def test_upsert_conversation_insert(self, storage):
        storage.upsert_conversation(**self._sample_conversation())
        assert storage.count_conversations() == 1

    def test_upsert_conversation_replaces_on_conflict(self, storage):
        storage.upsert_conversation(**self._sample_conversation(title="v1"))
        storage.upsert_conversation(**self._sample_conversation(title="v2"))
        assert storage.count_conversations() == 1
        meta = storage.get_conversation_meta("conv-001")
        assert meta is not None
        assert meta["title"] == "v2"

    def test_list_projects(self, storage):
        storage.upsert_conversation(**self._sample_conversation(project_id="a"))
        storage.upsert_conversation(
            **self._sample_conversation(conversation_id="conv-002", project_id="b")
        )
        projects = storage.list_projects()
        assert projects == ["a", "b"]

    def test_list_project_summaries(self, storage):
        storage.upsert_conversation(**self._sample_conversation())
        summaries = storage.list_project_summaries()
        assert len(summaries) == 1
        assert summaries[0]["project_id"] == "proj-alpha"
        assert summaries[0]["conversation_count"] == 1
        assert summaries[0]["message_count"] == 5

    def test_list_conversations_sort_and_filter(self, storage):
        for i in range(3):
            storage.upsert_conversation(
                **self._sample_conversation(
                    conversation_id=f"conv-{i}",
                    message_count=i + 1,
                )
            )
        results = storage.list_conversations(sort_by="length", limit=2)
        assert len(results) == 2
        assert results[0]["conversation_id"] == "conv-2"

    def test_list_conversations_filter_by_project(self, storage):
        storage.upsert_conversation(**self._sample_conversation(project_id="a"))
        storage.upsert_conversation(
            **self._sample_conversation(conversation_id="conv-002", project_id="b")
        )
        results = storage.list_conversations(project_id="a")
        assert len(results) == 1
        assert results[0]["project_id"] == "a"

    def test_list_conversations_filter_by_date(self, storage):
        storage.upsert_conversation(
            **self._sample_conversation(updated_at=datetime(2026, 6, 1))
        )
        results = storage.list_conversations(date_from=datetime(2026, 7, 1))
        assert len(results) == 0
        results = storage.list_conversations(date_from=datetime(2026, 5, 1))
        assert len(results) == 1

    def test_count_conversations(self, storage):
        for i in range(5):
            storage.upsert_conversation(
                **self._sample_conversation(conversation_id=f"conv-{i}")
            )
        assert storage.count_conversations() == 5
        assert storage.count_conversations(project_id="proj-alpha") == 5

    def test_get_conversation_meta_not_found(self, storage):
        assert storage.get_conversation_meta("nonexistent") is None

    def test_get_conversation_record_includes_messages(self, storage):
        storage.upsert_conversation(**self._sample_conversation())
        storage.insert_messages("conv-001", [
            {"sequence": 0, "role": "user", "content": "Hello"},
            {"sequence": 1, "role": "assistant", "content": "Hi there"},
        ])
        record = storage.get_conversation_record("conv-001")
        assert record is not None
        assert len(record["messages"]) == 2
        assert record["messages"][0]["role"] == "user"
        assert record["messages"][1]["content"] == "Hi there"

    def test_validate_parquet_scan_succeeds(self, storage):
        storage.validate_parquet_scan()  # should not raise

    def test_get_statistics_empty(self, storage):
        stats = storage.get_statistics()
        assert stats.total_conversations == 0
        assert stats.total_messages == 0

    def test_get_statistics_populated(self, storage):
        storage.upsert_conversation(**self._sample_conversation())
        stats = storage.get_statistics()
        assert stats.total_conversations == 1
        assert stats.total_messages == 5
        assert stats.total_projects == 1


# -- Messages --

class TestMessages:
    def test_insert_messages_replaces_existing(self, storage):
        storage.upsert_conversation(
            conversation_id="c1", project_id="p1",
            file_path="/f", title="t", created_at=datetime.now(),
            updated_at=datetime.now(), message_count=1,
            full_text="x", file_hash="h", indexed_at=datetime.now(),
        )
        storage.insert_messages("c1", [
            {"sequence": 0, "role": "user", "content": "first"},
        ])
        storage.insert_messages("c1", [
            {"sequence": 0, "role": "user", "content": "replaced"},
            {"sequence": 1, "role": "assistant", "content": "response"},
        ])
        record = storage.get_conversation_record("c1")
        assert record is not None
        assert len(record["messages"]) == 2
        assert record["messages"][0]["content"] == "replaced"


# -- Exchanges --

class TestExchanges:
    def test_upsert_exchange(self, storage):
        storage.upsert_exchange(
            exchange_id="ex-001",
            conversation_id="c1",
            project_id="p1",
            ply_start=0,
            ply_end=1,
            exchange_text="user: hi\nassistant: hello",
            created_at=datetime.now(),
        )
        assert storage.get_exchange_count() == 1

    def test_upsert_exchange_replaces(self, storage):
        kwargs = {
            "exchange_id": "ex-001",
            "conversation_id": "c1",
            "project_id": "p1",
            "ply_start": 0,
            "ply_end": 1,
            "exchange_text": "v1",
            "created_at": datetime.now(),
        }
        storage.upsert_exchange(**kwargs)
        storage.upsert_exchange(**{**kwargs, "exchange_text": "v2"})
        assert storage.get_exchange_count() == 1


# -- Embeddings --

class TestEmbeddings:
    def test_upsert_embedding_valid(self, storage):
        vec = [0.1] * EMBEDDING_DIM
        storage.upsert_embedding("ex-001", vec)
        assert storage.get_embedding_count() == 1

    def test_upsert_embedding_wrong_dimension_raises(self, storage):
        with pytest.raises(ValueError, match="dimension mismatch"):
            storage.upsert_embedding("ex-001", [0.1] * 10)


# -- File State --

class TestFileState:
    def test_upsert_file_state(self, storage):
        storage.upsert_file_state(
            file_path="/data/conv.jsonl",
            conversation_id="c1",
            project_id="p1",
            connector_name="claude",
            file_size=1024,
            file_hash="abc",
        )
        counts = storage.get_row_counts()
        assert counts["source_file_state"] == 1


# -- Code Blocks --

class TestCodeBlocks:
    def test_insert_code_block(self, storage):
        storage.insert_code_block(
            conversation_id="c1",
            project_id="p1",
            message_index=0,
            block_index=0,
            code="print('hello')",
            code_hash="hash1",
            lines=1,
        )
        counts = storage.get_row_counts()
        assert counts["code_blocks"] == 1
