"""Integration tests for v1 → v2 migration ETL."""
from __future__ import annotations

from datetime import datetime

import pyarrow as pa
import pyarrow.parquet as pq
import pytest

from searchat.models.schemas import (
    CODE_BLOCK_SCHEMA,
    CONVERSATION_SCHEMA,
    FILE_STATE_SCHEMA,
)
from searchat.storage.migration_v1_to_v2 import (
    _derive_exchanges,
    dry_run,
    migrate,
    verify,
)


@pytest.fixture()
def v1_data(tmp_path):
    """Create minimal v1 Parquet data for migration testing."""
    search_dir = tmp_path / ".searchat"
    data_dir = search_dir / "data"
    conv_dir = data_dir / "conversations"
    indices_dir = data_dir / "indices"
    code_dir = data_dir / "code"
    conv_dir.mkdir(parents=True)
    indices_dir.mkdir(parents=True)
    code_dir.mkdir(parents=True)

    # Write a conversation parquet
    now = datetime.now()
    conv_table = pa.table(
        {
            "conversation_id": ["c1", "c2"],
            "project_id": ["proj", "proj"],
            "file_path": ["/a.jsonl", "/b.jsonl"],
            "title": ["Conv 1", "Conv 2"],
            "created_at": [now, now],
            "updated_at": [now, now],
            "message_count": [2, 1],
            "messages": [
                [
                    {"sequence": 0, "role": "user", "content": "Hello",
                     "timestamp": now, "has_code": False, "code_blocks": None},
                    {"sequence": 1, "role": "assistant", "content": "Hi",
                     "timestamp": now, "has_code": False, "code_blocks": None},
                ],
                [
                    {"sequence": 0, "role": "user", "content": "Question",
                     "timestamp": now, "has_code": False, "code_blocks": None},
                ],
            ],
            "full_text": ["Hello Hi", "Question"],
            "embedding_id": [0, 1],
            "file_hash": ["h1", "h2"],
            "indexed_at": [now, now],
            "files_mentioned": [None, None],
            "git_branch": [None, None],
        },
        schema=CONVERSATION_SCHEMA,
    )
    pq.write_table(conv_table, conv_dir / "project_proj.parquet")

    # Write file_state parquet
    fs_table = pa.table(
        {
            "file_path": ["/a.jsonl", "/b.jsonl"],
            "file_hash": ["h1", "h2"],
            "file_size": [100, 200],
            "indexed_at": [now, now],
            "connector_name": ["claude", "claude"],
            "conversation_id": ["c1", "c2"],
            "project_id": ["proj", "proj"],
        },
        schema=FILE_STATE_SCHEMA,
    )
    pq.write_table(fs_table, indices_dir / "file_state.parquet")

    # Write code blocks parquet
    code_table = pa.table(
        {
            "conversation_id": ["c1"],
            "project_id": ["proj"],
            "connector": ["claude"],
            "file_path": ["/a.jsonl"],
            "title": ["Conv 1"],
            "conversation_created_at": [now],
            "conversation_updated_at": [now],
            "message_index": [1],
            "block_index": [0],
            "role": ["assistant"],
            "message_timestamp": [now],
            "fence_language": ["python"],
            "language": ["python"],
            "language_source": ["fence"],
            "functions": [["foo"]],
            "classes": [None],
            "imports": [["os"]],
            "code": ["print('hello')"],
            "code_hash": ["ch1"],
            "lines": [1],
        },
        schema=CODE_BLOCK_SCHEMA,
    )
    pq.write_table(code_table, code_dir / "project_proj.parquet")

    return search_dir


class TestDryRun:
    def test_dry_run_scans_parquets(self, v1_data, tmp_path):
        duckdb_path = tmp_path / "out.duckdb"
        report = dry_run(v1_data, duckdb_path)
        assert report.conversation_parquets == 1
        assert report.total_conversations == 2
        assert report.estimated_messages == 3
        assert report.file_state_rows == 2
        assert report.code_parquets == 1
        assert report.code_block_rows == 1

    def test_dry_run_empty_dir(self, tmp_path):
        empty_dir = tmp_path / "empty"
        empty_dir.mkdir()
        (empty_dir / "data").mkdir()
        report = dry_run(empty_dir, tmp_path / "out.duckdb")
        assert report.total_conversations == 0


class TestMigrate:
    def test_migrate_populates_all_tables(self, v1_data, tmp_path):
        duckdb_path = tmp_path / "migrated.duckdb"
        stats = migrate(v1_data, duckdb_path)

        assert stats.conversations == 2
        assert stats.messages == 3
        assert stats.exchanges > 0
        assert stats.file_states == 2
        assert stats.code_blocks == 1
        assert not stats.errors

    def test_migrate_creates_exchanges_from_messages(self, v1_data, tmp_path):
        duckdb_path = tmp_path / "migrated.duckdb"
        stats = migrate(v1_data, duckdb_path)
        # conv c1 has user+assistant → 1 exchange
        # conv c2 has user only → 1 exchange
        assert stats.exchanges == 2


class TestVerify:
    def test_verify_after_migration_matches(self, v1_data, tmp_path):
        duckdb_path = tmp_path / "verified.duckdb"
        migrate(v1_data, duckdb_path)
        result = verify(v1_data, duckdb_path)

        assert result["conversations"]["v1"] == result["conversations"]["v2"]
        assert result["messages"]["v1"] == result["messages"]["v2"]
        assert result["source_file_state"]["v1"] == result["source_file_state"]["v2"]
        assert result["code_blocks"]["v1"] == result["code_blocks"]["v2"]


class TestDeriveExchanges:
    def test_single_user_assistant_pair(self):
        messages = [
            {"sequence": 0, "role": "user", "content": "Hello"},
            {"sequence": 1, "role": "assistant", "content": "Hi"},
        ]
        exchanges = _derive_exchanges("c1", "p1", messages, datetime.now())
        assert len(exchanges) == 1
        assert exchanges[0]["ply_start"] == 0
        assert exchanges[0]["ply_end"] == 1
        assert "Hello" in exchanges[0]["exchange_text"]
        assert "Hi" in exchanges[0]["exchange_text"]

    def test_multiple_exchanges(self):
        messages = [
            {"sequence": 0, "role": "user", "content": "Q1"},
            {"sequence": 1, "role": "assistant", "content": "A1"},
            {"sequence": 2, "role": "user", "content": "Q2"},
            {"sequence": 3, "role": "assistant", "content": "A2"},
        ]
        exchanges = _derive_exchanges("c1", "p1", messages, datetime.now())
        assert len(exchanges) == 2
        assert exchanges[0]["ply_start"] == 0
        assert exchanges[0]["ply_end"] == 1
        assert exchanges[1]["ply_start"] == 2
        assert exchanges[1]["ply_end"] == 3

    def test_user_only_message(self):
        messages = [
            {"sequence": 0, "role": "user", "content": "Hello"},
        ]
        exchanges = _derive_exchanges("c1", "p1", messages, datetime.now())
        assert len(exchanges) == 1

    def test_empty_messages(self):
        exchanges = _derive_exchanges("c1", "p1", [], datetime.now())
        assert exchanges == []

    def test_assistant_first(self):
        messages = [
            {"sequence": 0, "role": "assistant", "content": "System msg"},
            {"sequence": 1, "role": "user", "content": "Hello"},
            {"sequence": 2, "role": "assistant", "content": "Hi"},
        ]
        exchanges = _derive_exchanges("c1", "p1", messages, datetime.now())
        assert len(exchanges) == 2
