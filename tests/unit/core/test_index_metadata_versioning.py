import json
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq
import pytest

from searchat.config import Config
from searchat.config.constants import INDEX_FORMAT, INDEX_FORMAT_VERSION, INDEX_SCHEMA_VERSION
from searchat.core.search_engine import SearchEngine
from searchat.models import CONVERSATION_SCHEMA


def _write_empty_parquet(path: Path) -> None:
    table = pa.Table.from_pylist([], schema=CONVERSATION_SCHEMA)
    pq.write_table(table, path)


def test_schema_version_mismatch(tmp_path):
    search_dir = tmp_path / "search"
    conversations_dir = search_dir / "data" / "conversations"
    indices_dir = search_dir / "data" / "indices"
    conversations_dir.mkdir(parents=True)
    indices_dir.mkdir(parents=True)

    _write_empty_parquet(conversations_dir / "project_test.parquet")

    metadata_path = indices_dir / "index_metadata.json"
    metadata = {
        "schema_version": "0.9",
        "index_format_version": INDEX_FORMAT_VERSION,
        "created_at": "2025-01-01T00:00:00",
        "embedding_model": Config.load().embedding.model,
        "format": INDEX_FORMAT,
        "last_updated": "2025-01-01T00:00:00",
        "total_conversations": 0,
        "total_chunks": 0,
        "chunk_size": 1500,
        "chunk_overlap": 200,
        "next_vector_id": 0,
    }
    metadata_path.write_text(json.dumps(metadata), encoding="utf-8")

    engine = SearchEngine(search_dir, Config.load())
    with pytest.raises(ValueError):
        engine._validate_index_metadata()


def test_index_format_version_mismatch(tmp_path):
    search_dir = tmp_path / "search"
    conversations_dir = search_dir / "data" / "conversations"
    indices_dir = search_dir / "data" / "indices"
    conversations_dir.mkdir(parents=True)
    indices_dir.mkdir(parents=True)

    _write_empty_parquet(conversations_dir / "project_test.parquet")

    metadata_path = indices_dir / "index_metadata.json"
    metadata = {
        "schema_version": INDEX_SCHEMA_VERSION,
        "index_format_version": "0.1",
        "created_at": "2025-01-01T00:00:00",
        "embedding_model": Config.load().embedding.model,
        "format": INDEX_FORMAT,
        "last_updated": "2025-01-01T00:00:00",
        "total_conversations": 0,
        "total_chunks": 0,
        "chunk_size": 1500,
        "chunk_overlap": 200,
        "next_vector_id": 0,
    }
    metadata_path.write_text(json.dumps(metadata), encoding="utf-8")

    engine = SearchEngine(search_dir, Config.load())
    with pytest.raises(ValueError):
        engine._validate_index_metadata()
