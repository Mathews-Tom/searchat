"""Integration tests for the DualWriter proxy."""
from __future__ import annotations

from datetime import datetime
from unittest.mock import MagicMock

import pytest

from searchat.storage.dual_writer import DualWriter
from searchat.storage.unified_storage import UnifiedStorage


@pytest.fixture()
def duckdb_backend(tmp_path):
    db_path = tmp_path / "dual_test.duckdb"
    s = UnifiedStorage(db_path)
    yield s
    s.close()


@pytest.fixture()
def parquet_backend():
    """Mock the Parquet backend for read delegation."""
    mock = MagicMock()
    mock.list_projects.return_value = ["project-a"]
    mock.list_project_summaries.return_value = [
        {"project_id": "project-a", "conversation_count": 1, "message_count": 5}
    ]
    mock.list_conversations.return_value = [{"conversation_id": "c1"}]
    mock.count_conversations.return_value = 1
    mock.get_conversation_meta.return_value = {"conversation_id": "c1"}
    mock.get_conversation_record.return_value = {"conversation_id": "c1", "messages": []}
    mock.get_statistics.return_value = MagicMock(total_conversations=1)
    mock.validate_parquet_scan.return_value = None
    return mock


@pytest.fixture()
def dual(parquet_backend, duckdb_backend):
    return DualWriter(parquet_backend, duckdb_backend)


class TestDualWriterReads:
    """All reads delegate to the Parquet backend."""

    def test_list_projects_delegates(self, dual, parquet_backend):
        result = dual.list_projects()
        parquet_backend.list_projects.assert_called_once()
        assert result == ["project-a"]

    def test_list_project_summaries_delegates(self, dual, parquet_backend):
        result = dual.list_project_summaries()
        parquet_backend.list_project_summaries.assert_called_once()
        assert len(result) == 1

    def test_list_conversations_delegates(self, dual, parquet_backend):
        result = dual.list_conversations(sort_by="length", limit=10)
        parquet_backend.list_conversations.assert_called_once()
        assert len(result) == 1

    def test_count_conversations_delegates(self, dual, parquet_backend):
        result = dual.count_conversations()
        parquet_backend.count_conversations.assert_called_once()
        assert result == 1

    def test_validate_parquet_scan_delegates(self, dual, parquet_backend):
        dual.validate_parquet_scan()
        parquet_backend.validate_parquet_scan.assert_called_once()

    def test_get_conversation_meta_delegates(self, dual, parquet_backend):
        result = dual.get_conversation_meta("c1")
        parquet_backend.get_conversation_meta.assert_called_once_with("c1")
        assert result is not None

    def test_get_conversation_record_delegates(self, dual, parquet_backend):
        result = dual.get_conversation_record("c1")
        parquet_backend.get_conversation_record.assert_called_once_with("c1")
        assert result is not None

    def test_get_statistics_delegates(self, dual, parquet_backend):
        result = dual.get_statistics()
        parquet_backend.get_statistics.assert_called_once()
        assert result.total_conversations == 1


class TestDualWriterWrites:
    """Write operations forward to the DuckDB backend."""

    def test_write_conversation_populates_duckdb(self, dual, duckdb_backend):
        dual.write_conversation(
            conversation_id="c1",
            project_id="p1",
            file_path="/f",
            title="Test",
            created_at=datetime(2026, 1, 1),
            updated_at=datetime(2026, 1, 2),
            message_count=2,
            full_text="hello world",
            file_hash="h1",
            indexed_at=datetime(2026, 1, 3),
            messages=[
                {"sequence": 0, "role": "user", "content": "hello"},
                {"sequence": 1, "role": "assistant", "content": "hi"},
            ],
        )
        assert duckdb_backend.count_conversations() == 1
        record = duckdb_backend.get_conversation_record("c1")
        assert record is not None
        assert len(record["messages"]) == 2

    def test_write_conversation_duckdb_failure_logs_not_raises(
        self, parquet_backend, duckdb_backend, caplog
    ):
        """DuckDB write failure must not propagate."""
        duckdb_backend.close()  # force closed connection
        dual = DualWriter(parquet_backend, duckdb_backend)

        # Should not raise
        dual.write_conversation(
            conversation_id="c1",
            project_id="p1",
            file_path="/f",
            title="Test",
            created_at=datetime(2026, 1, 1),
            updated_at=datetime(2026, 1, 2),
            message_count=0,
            full_text="",
            file_hash="h",
            indexed_at=datetime(2026, 1, 3),
        )
        assert "DuckDB dual-write failed" in caplog.text

    def test_write_file_state_populates_duckdb(self, dual, duckdb_backend):
        dual.write_file_state(
            file_path="/data/conv.jsonl",
            conversation_id="c1",
            project_id="p1",
            connector_name="claude",
            file_size=512,
            file_hash="abc",
        )
        counts = duckdb_backend.get_row_counts()
        assert counts["source_file_state"] == 1

    def test_write_code_block_populates_duckdb(self, dual, duckdb_backend):
        dual.write_code_block(
            conversation_id="c1",
            project_id="p1",
            message_index=0,
            block_index=0,
            code="x = 1",
            code_hash="h",
            lines=1,
        )
        counts = duckdb_backend.get_row_counts()
        assert counts["code_blocks"] == 1
