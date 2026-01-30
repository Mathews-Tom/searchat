import json
from pathlib import Path

import numpy as np
import pytest

from searchat.config import PathResolver
from searchat.core import ConversationIndexer


def _write_jsonl(path: Path, lines: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        for line in lines:
            f.write(json.dumps(line) + "\n")


def _fake_encode(self, chunks_with_meta, progress=None):
    return np.zeros((len(chunks_with_meta), 2), dtype=np.float32)


@pytest.fixture
def claude_project_dir(tmp_path, monkeypatch):
    claude_dir = tmp_path / ".claude" / "projects"
    monkeypatch.setattr(PathResolver, "resolve_claude_dirs", lambda config=None: [claude_dir])
    monkeypatch.setattr(PathResolver, "resolve_vibe_dirs", lambda: [])
    monkeypatch.setattr(PathResolver, "resolve_opencode_dirs", lambda config=None: [])
    return claude_dir


def test_adaptive_reindex_updates_vectors(tmp_path, claude_project_dir, monkeypatch):
    monkeypatch.setattr(ConversationIndexer, "_batch_encode_chunks", _fake_encode)
    search_dir = tmp_path / "search"
    indexer = ConversationIndexer(search_dir)

    conv_path = claude_project_dir / "project-one" / "conv1.jsonl"
    _write_jsonl(
        conv_path,
        [
            {"type": "user", "message": {"content": "Hello"}, "timestamp": "2025-09-01T10:00:00"},
            {"type": "assistant", "message": {"content": "Hi"}, "timestamp": "2025-09-01T10:00:30"},
        ],
    )

    indexer.index_all()

    metadata_path = search_dir / "data" / "indices" / "embeddings.metadata.parquet"
    metadata_table = metadata_path
    assert metadata_table.exists()

    _write_jsonl(
        conv_path,
        [
            {"type": "user", "message": {"content": "Hello again"}, "timestamp": "2025-09-02T10:00:00"},
            {"type": "assistant", "message": {"content": "Hi again"}, "timestamp": "2025-09-02T10:00:30"},
        ],
    )

    stats = indexer.index_adaptive([str(conv_path)])
    assert stats.updated_conversations == 1

    import pyarrow.parquet as pq

    updated_table = pq.read_table(metadata_path)
    vector_ids = sorted(updated_table.column("vector_id").to_pylist())
    assert vector_ids == [1]

    with open(search_dir / "data" / "indices" / "index_metadata.json", "r", encoding="utf-8") as f:
        metadata = json.load(f)
    assert metadata["next_vector_id"] == 2

    stats_skip = indexer.index_adaptive([str(conv_path)])
    assert stats_skip.skipped_conversations == 1

    conv2_path = claude_project_dir / "project-one" / "conv2.jsonl"
    _write_jsonl(
        conv2_path,
        [
            {"type": "user", "message": {"content": "New"}, "timestamp": "2025-09-03T10:00:00"},
            {"type": "assistant", "message": {"content": "Conversation"}, "timestamp": "2025-09-03T10:00:30"},
        ],
    )

    stats_new = indexer.index_adaptive([str(conv2_path)])
    assert stats_new.new_conversations == 1

    updated_table = pq.read_table(metadata_path)
    vector_ids = sorted(updated_table.column("vector_id").to_pylist())
    assert vector_ids == [1, 2]

    file_state_path = search_dir / "data" / "indices" / "file_state.parquet"
    assert file_state_path.exists()
    file_state_table = pq.read_table(file_state_path)
    assert len(file_state_table) == 2
