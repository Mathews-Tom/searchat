from __future__ import annotations

from pathlib import Path

import pytest

from searchat.config.constants import INDEX_FORMAT, INDEX_FORMAT_VERSION, INDEX_SCHEMA_VERSION
from searchat.services.storage_contracts import (
    BACKUP_MANIFEST_VERSION,
    BackupManifest,
    BackupMetadata,
    IndexMetadata,
    StorageCompatibilityError,
    read_index_metadata,
    write_index_metadata,
)


def test_index_metadata_round_trip_and_validation(tmp_path: Path) -> None:
    search_dir = tmp_path / "search"
    metadata = IndexMetadata(
        schema_version=INDEX_SCHEMA_VERSION,
        index_format_version=INDEX_FORMAT_VERSION,
        created_at="2026-03-15T00:00:00",
        embedding_model="all-MiniLM-L6-v2",
        format=INDEX_FORMAT,
        last_updated="2026-03-15T01:00:00",
        total_conversations=4,
        total_chunks=9,
        chunk_size=1500,
        chunk_overlap=200,
        next_vector_id=9,
    )

    write_index_metadata(search_dir, metadata)

    loaded = read_index_metadata(search_dir)
    assert loaded == metadata
    loaded.validate_compatible(embedding_model="all-MiniLM-L6-v2")


def test_backup_metadata_defaults_missing_version_field() -> None:
    metadata = BackupMetadata.from_dict(
        {
            "timestamp": "20260315_120000",
            "backup_path": "/tmp/backup_20260315_120000",
            "source_path": "/tmp/search",
            "file_count": 3,
            "total_size_bytes": 42,
            "backup_type": "manual",
        }
    )

    assert metadata.metadata_version == 1
    assert metadata.backup_type == "manual"


def test_backup_manifest_rejects_unsupported_version() -> None:
    with pytest.raises(StorageCompatibilityError, match="manifest version mismatch"):
        BackupManifest.from_dict(
            {
                "manifest_version": BACKUP_MANIFEST_VERSION + 1,
                "backup_mode": "full",
                "encrypted": False,
                "created_at": "2026-03-15T00:00:00",
                "parent_name": None,
                "files": {},
                "deleted_files": [],
            }
        )
