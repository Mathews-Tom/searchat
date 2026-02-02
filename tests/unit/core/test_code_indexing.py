from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pyarrow.parquet as pq
import pytest

from searchat.config import PathResolver
from searchat.core.indexer import ConversationIndexer


def _write_jsonl(path: Path, lines: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        for line in lines:
            f.write(json.dumps(line) + "\n")


def _fake_encode(self, chunks_with_meta, progress=None):  # noqa: ANN001
    return np.zeros((len(chunks_with_meta), 2), dtype=np.float32)


@pytest.mark.unit
def test_index_all_writes_code_blocks_parquet(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(ConversationIndexer, "_batch_encode_chunks", _fake_encode)

    claude_dir = tmp_path / ".claude" / "projects"
    monkeypatch.setattr(PathResolver, "resolve_claude_dirs", staticmethod(lambda _cfg=None: [claude_dir]))
    monkeypatch.setattr(PathResolver, "resolve_vibe_dirs", staticmethod(lambda: []))
    monkeypatch.setattr(PathResolver, "resolve_opencode_dirs", staticmethod(lambda _cfg=None: []))

    conv_path = claude_dir / "project-one" / "conv1.jsonl"
    _write_jsonl(
        conv_path,
        [
            {"type": "user", "message": {"content": "Hello"}, "timestamp": "2025-09-01T10:00:00"},
            {
                "type": "assistant",
                "message": {
                    "content": "Here is code:\n```python\nprint('hi')\n```\n",
                },
                "timestamp": "2025-09-01T10:00:30",
            },
        ],
    )

    search_dir = tmp_path / "search"
    indexer = ConversationIndexer(search_dir)
    indexer.index_all()

    code_dir = search_dir / "data" / "code"
    files = list(code_dir.glob("*.parquet"))
    assert files, "expected code parquet files"

    table = pq.read_table(files[0])
    assert table.num_rows >= 1
    assert "code" in table.column_names
    assert "language" in table.column_names
