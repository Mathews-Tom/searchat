"""Integration tests for UnifiedIndexer — end-to-end DuckDB write path."""
from __future__ import annotations

from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from searchat.core.unified_indexer import UnifiedIndexer
from searchat.models import ConversationRecord, MessageRecord
from searchat.storage.unified_storage import UnifiedStorage


def _make_storage(tmp_path: Path) -> UnifiedStorage:
    """Create a real DuckDB storage instance for integration tests."""
    db_path = tmp_path / "test.duckdb"
    return UnifiedStorage(str(db_path))


def _make_config() -> MagicMock:
    """Create a mock config with required fields."""
    config = MagicMock()
    config.indexing.enable_connectors = True
    config.embedding.batch_size = 32
    config.embedding.model = "all-MiniLM-L6-v2"
    config.expertise.enabled = False
    config.storage.resolve_duckdb_path.return_value = Path("/unused")
    config.storage.hnsw_ef_construction = 128
    config.storage.hnsw_ef_search = 64
    config.storage.hnsw_m = 16
    return config


def _make_record(
    file_path: str,
    conversation_id: str = "conv-1",
    n_messages: int = 4,
) -> ConversationRecord:
    """Create a ConversationRecord with N messages (alternating user/assistant)."""
    now = datetime.now()
    messages = []
    for i in range(n_messages):
        role = "user" if i % 2 == 0 else "assistant"
        messages.append(
            MessageRecord(
                sequence=i,
                role=role,
                content=f"Message {i} from {role}",
                timestamp=now,
                has_code=False,
            )
        )
    return ConversationRecord(
        conversation_id=conversation_id,
        project_id="proj-1",
        file_path=file_path,
        title="Integration Test Conversation",
        created_at=now,
        updated_at=now,
        message_count=len(messages),
        messages=messages,
        full_text="\n".join(m.content for m in messages),
        embedding_id=0,
        file_hash="integration_hash_123",
        indexed_at=now,
    )


class TestUnifiedIndexerIntegration:
    def test_index_writes_to_duckdb(self, tmp_path: Path) -> None:
        """Full pipeline: parse → write conversation + messages + exchanges + file_state."""
        storage = _make_storage(tmp_path)
        config = _make_config()

        convo_file = tmp_path / "test_conv.jsonl"
        convo_file.write_text("")

        record = _make_record(str(convo_file))
        fake_connector = MagicMock()
        fake_connector.name = "test"
        fake_connector.parse.return_value = record

        fake_embedder = MagicMock()
        fake_embedder.encode.return_value = [[0.1] * 384, [0.2] * 384]

        indexer = UnifiedIndexer(tmp_path, config, storage=storage)

        with (
            patch("searchat.core.unified_indexer.detect_connector", return_value=fake_connector),
            patch.object(indexer, "_get_embedder", return_value=fake_embedder),
        ):
            stats = indexer.index_append_only([str(convo_file)])

        assert stats.new_conversations == 1
        assert stats.empty_conversations == 0

        # Verify conversation written to DuckDB
        cur = storage._read_cursor()
        convs = cur.execute("SELECT conversation_id, title FROM conversations").fetchall()
        assert len(convs) == 1
        assert convs[0][0] == "conv-1"
        assert convs[0][1] == "Integration Test Conversation"

        # Verify messages written
        msgs = cur.execute(
            "SELECT sequence, role, content FROM messages WHERE conversation_id = 'conv-1' ORDER BY sequence"
        ).fetchall()
        assert len(msgs) == 4
        assert msgs[0][1] == "user"
        assert msgs[1][1] == "assistant"

        # Verify exchanges written
        exchanges = cur.execute(
            "SELECT exchange_id, ply_start, ply_end FROM exchanges WHERE conversation_id = 'conv-1'"
        ).fetchall()
        assert len(exchanges) == 2  # 4 messages → 2 user→assistant exchanges

        # Verify file state written
        file_states = cur.execute(
            "SELECT file_path, conversation_id, connector_name FROM source_file_state"
        ).fetchall()
        assert len(file_states) == 1
        assert file_states[0][0] == str(convo_file)
        assert file_states[0][2] == "test"

    def test_indexed_files_appear_in_get_indexed_file_paths(self, tmp_path: Path) -> None:
        storage = _make_storage(tmp_path)
        config = _make_config()

        convo_file = tmp_path / "tracked.jsonl"
        convo_file.write_text("")

        record = _make_record(str(convo_file))
        fake_connector = MagicMock()
        fake_connector.name = "test"
        fake_connector.parse.return_value = record

        fake_embedder = MagicMock()
        fake_embedder.encode.return_value = [[0.1] * 384, [0.2] * 384]

        indexer = UnifiedIndexer(tmp_path, config, storage=storage)

        # Before indexing
        assert indexer.get_indexed_file_paths() == set()

        with (
            patch("searchat.core.unified_indexer.detect_connector", return_value=fake_connector),
            patch.object(indexer, "_get_embedder", return_value=fake_embedder),
        ):
            indexer.index_append_only([str(convo_file)])

        # After indexing
        paths = indexer.get_indexed_file_paths()
        assert str(convo_file) in paths

    def test_duplicate_files_skipped(self, tmp_path: Path) -> None:
        storage = _make_storage(tmp_path)
        config = _make_config()

        convo_file = tmp_path / "dup.jsonl"
        convo_file.write_text("")

        record = _make_record(str(convo_file))
        fake_connector = MagicMock()
        fake_connector.name = "test"
        fake_connector.parse.return_value = record

        fake_embedder = MagicMock()
        fake_embedder.encode.return_value = [[0.1] * 384, [0.2] * 384]

        indexer = UnifiedIndexer(tmp_path, config, storage=storage)

        with (
            patch("searchat.core.unified_indexer.detect_connector", return_value=fake_connector),
            patch.object(indexer, "_get_embedder", return_value=fake_embedder),
        ):
            stats1 = indexer.index_append_only([str(convo_file)])
            stats2 = indexer.index_append_only([str(convo_file)])

        assert stats1.new_conversations == 1
        assert stats2.new_conversations == 0
        assert stats2.skipped_conversations == 1

    def test_multiple_conversations_indexed(self, tmp_path: Path) -> None:
        storage = _make_storage(tmp_path)
        config = _make_config()

        files = []
        records = []
        for i in range(3):
            f = tmp_path / f"conv_{i}.jsonl"
            f.write_text("")
            files.append(str(f))
            records.append(_make_record(str(f), conversation_id=f"conv-{i}"))

        fake_connector = MagicMock()
        fake_connector.name = "test"
        fake_connector.parse.side_effect = records

        fake_embedder = MagicMock()
        fake_embedder.encode.return_value = [[0.1] * 384, [0.2] * 384]

        indexer = UnifiedIndexer(tmp_path, config, storage=storage)

        with (
            patch("searchat.core.unified_indexer.detect_connector", return_value=fake_connector),
            patch.object(indexer, "_get_embedder", return_value=fake_embedder),
        ):
            stats = indexer.index_append_only(files)

        assert stats.new_conversations == 3

        cur = storage._read_cursor()
        count = cur.execute("SELECT count(*) FROM conversations").fetchone()[0]
        assert count == 3

    def test_safety_guard_index_all_raises(self, tmp_path: Path) -> None:
        storage = _make_storage(tmp_path)
        indexer = UnifiedIndexer(tmp_path, storage=storage)
        with pytest.raises(RuntimeError, match="Existing index detected"):
            indexer.index_all()

    def test_exchange_segmentation_writes_correct_data(self, tmp_path: Path) -> None:
        """Verify exchange content and ply ranges are correct in DuckDB."""
        storage = _make_storage(tmp_path)
        config = _make_config()

        convo_file = tmp_path / "exchanges.jsonl"
        convo_file.write_text("")

        now = datetime.now()
        messages = [
            MessageRecord(sequence=0, role="user", content="What is Python?", timestamp=now, has_code=False),
            MessageRecord(sequence=1, role="assistant", content="Python is a language.", timestamp=now, has_code=False),
            MessageRecord(sequence=2, role="user", content="How about Rust?", timestamp=now, has_code=False),
            MessageRecord(sequence=3, role="assistant", content="Rust is systems programming.", timestamp=now, has_code=False),
            MessageRecord(sequence=4, role="assistant", content="It has memory safety.", timestamp=now, has_code=False),
        ]
        record = ConversationRecord(
            conversation_id="conv-exchanges",
            project_id="proj-1",
            file_path=str(convo_file),
            title="Exchange Test",
            created_at=now,
            updated_at=now,
            message_count=len(messages),
            messages=messages,
            full_text="\n".join(m.content for m in messages),
            embedding_id=0,
            file_hash="exc_hash",
            indexed_at=now,
        )

        fake_connector = MagicMock()
        fake_connector.name = "test"
        fake_connector.parse.return_value = record

        fake_embedder = MagicMock()
        fake_embedder.encode.return_value = [[0.1] * 384, [0.2] * 384]

        indexer = UnifiedIndexer(tmp_path, config, storage=storage)

        with (
            patch("searchat.core.unified_indexer.detect_connector", return_value=fake_connector),
            patch.object(indexer, "_get_embedder", return_value=fake_embedder),
        ):
            indexer.index_append_only([str(convo_file)])

        cur = storage._read_cursor()
        exchanges = cur.execute(
            "SELECT ply_start, ply_end, exchange_text FROM exchanges "
            "WHERE conversation_id = 'conv-exchanges' ORDER BY ply_start"
        ).fetchall()

        assert len(exchanges) == 2

        # First exchange: user Q + assistant A (ply 0-1)
        assert exchanges[0][0] == 0  # ply_start
        assert exchanges[0][1] == 1  # ply_end
        assert "What is Python?" in exchanges[0][2]
        assert "Python is a language." in exchanges[0][2]

        # Second exchange: user Q + two assistant messages (ply 2-4)
        assert exchanges[1][0] == 2
        assert exchanges[1][1] == 4
        assert "How about Rust?" in exchanges[1][2]
        assert "Rust is systems programming." in exchanges[1][2]
        assert "memory safety" in exchanges[1][2]
