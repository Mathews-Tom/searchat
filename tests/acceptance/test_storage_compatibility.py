from __future__ import annotations

import json
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq

from searchat.config import Config
from searchat.config.constants import INDEX_FORMAT, INDEX_FORMAT_VERSION, INDEX_SCHEMA_VERSION
from searchat.core.search_engine import SearchEngine
from searchat.models import CONVERSATION_SCHEMA
from searchat.services.backup import BackupManager
from searchat.services.storage_contracts import (
    BACKUP_MANIFEST_FILE,
    IndexMetadata,
    write_index_metadata,
)


def _write_empty_conversation_parquet(path: Path) -> None:
    table = pa.Table.from_pylist([], schema=CONVERSATION_SCHEMA)
    pq.write_table(table, path)


def test_storage_compatibility_current_index_metadata_is_loadable(tmp_path: Path) -> None:
    search_dir = tmp_path / "search"
    conversations_dir = search_dir / "data" / "conversations"
    indices_dir = search_dir / "data" / "indices"
    conversations_dir.mkdir(parents=True)
    indices_dir.mkdir(parents=True)

    _write_empty_conversation_parquet(conversations_dir / "project_test.parquet")
    (indices_dir / "embeddings.metadata.parquet").write_bytes(b"PAR1")

    metadata = IndexMetadata(
        schema_version=INDEX_SCHEMA_VERSION,
        index_format_version=INDEX_FORMAT_VERSION,
        created_at="2026-03-15T00:00:00",
        embedding_model=Config.load().embedding.model,
        format=INDEX_FORMAT,
        last_updated="2026-03-15T00:00:00",
        total_conversations=0,
        total_chunks=0,
        next_vector_id=0,
    )
    write_index_metadata(search_dir, metadata)

    engine = SearchEngine(search_dir, Config.load())
    engine._validate_index_metadata()


def test_storage_compatibility_legacy_backup_metadata_remains_listable(temp_search_dir: Path) -> None:
    manager = BackupManager(temp_search_dir)
    live_file = temp_search_dir / "data" / "conversations" / "conv.parquet"
    live_file.parent.mkdir(parents=True, exist_ok=True)
    live_file.write_bytes(b"PAR1\n")

    backup = manager.create_backup(backup_name="compat")
    metadata_path = backup.backup_path / manager.METADATA_FILE
    payload = json.loads(metadata_path.read_text(encoding="utf-8"))
    payload.pop("metadata_version", None)
    metadata_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    listed = manager.list_backups()
    assert listed
    assert listed[0].backup_path == backup.backup_path


def test_storage_compatibility_invalid_manifest_version_fails_closed(temp_search_dir: Path) -> None:
    manager = BackupManager(temp_search_dir)
    live_file = temp_search_dir / "data" / "conversations" / "conv.parquet"
    live_file.parent.mkdir(parents=True, exist_ok=True)
    live_file.write_bytes(b"PAR1\n")

    backup = manager.create_backup(backup_name="invalid-manifest")
    manifest_path = backup.backup_path / BACKUP_MANIFEST_FILE
    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    payload["manifest_version"] = 999
    manifest_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    result = manager.validate_backup_artifact(backup.backup_path.name, verify_hashes=False)
    assert result["valid"] is False
    assert any("manifest version mismatch" in error for error in result["errors"])
