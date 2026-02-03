from __future__ import annotations

import json
from pathlib import Path

import pytest

from searchat.config import Config
from searchat.config.constants import (
    INDEX_FORMAT,
    INDEX_FORMAT_VERSION,
    INDEX_METADATA_FILENAME,
    INDEX_SCHEMA_VERSION,
)
from searchat.core.search_engine import SearchEngine


@pytest.mark.unit
def test_faiss_mmap_uses_read_index_flags(monkeypatch: pytest.MonkeyPatch, temp_search_dir: Path):
    cfg = Config.load()
    cfg.performance.faiss_mmap = True

    # Minimal on-disk artifacts to satisfy SearchEngine validations.
    (temp_search_dir / "data" / "conversations").mkdir(parents=True, exist_ok=True)
    (temp_search_dir / "data" / "conversations" / "c.parquet").write_bytes(b"")

    indices = temp_search_dir / "data" / "indices"
    indices.mkdir(parents=True, exist_ok=True)
    (indices / "embeddings.metadata.parquet").write_bytes(b"")
    (indices / "embeddings.faiss").write_bytes(b"")

    meta = {
        "embedding_model": cfg.embedding.model,
        "format": INDEX_FORMAT,
        "schema_version": INDEX_SCHEMA_VERSION,
        "index_format_version": INDEX_FORMAT_VERSION,
    }
    (indices / INDEX_METADATA_FILENAME).write_text(json.dumps(meta), encoding="utf-8")

    called: dict[str, object] = {}

    import searchat.core.search_engine as se

    def _fake_read_index(path: str, flags: int | None = None):
        called["path"] = path
        called["flags"] = flags
        return object()

    monkeypatch.setattr(se.faiss, "read_index", _fake_read_index)
    # Some tests run with faiss mocked; ensure flags are ints.
    monkeypatch.setattr(se.faiss, "IO_FLAG_MMAP", 1, raising=False)
    monkeypatch.setattr(se.faiss, "IO_FLAG_READ_ONLY", 2, raising=False)

    engine = SearchEngine(temp_search_dir, cfg)
    engine.ensure_faiss_loaded()

    assert called["path"].endswith("embeddings.faiss")
    assert isinstance(called["flags"], int)
