from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

from searchat.services.storage_contracts import IndexMetadata
from searchat.services.storage_migrations import (
    migrate_backup_manifest,
    migrate_backup_metadata,
    migrate_index_metadata_file,
    migrate_index_metadata_root,
    plan_backup_manifest_migration,
    plan_backup_metadata_migration,
    plan_index_metadata_migration,
)


def test_plan_index_metadata_migration_backfills_normalizable_fields() -> None:
    metadata = IndexMetadata(
        schema_version="1.2",
        index_format_version="1.0",
        created_at="2026-03-01T00:00:00",
        embedding_model="",
        format="parquet+faiss",
        total_conversations=2,
        total_chunks=5,
        next_vector_id=0,
    )

    plan = plan_index_metadata_migration(metadata, embedding_model="all-MiniLM-L6-v2")

    assert plan.has_changes is True
    assert set(plan.changed_fields) >= {"embedding_model", "last_updated", "chunk_size", "chunk_overlap", "next_vector_id"}
    assert plan.migrated.embedding_model == "all-MiniLM-L6-v2"
    assert plan.migrated.next_vector_id == 5


def test_migrate_index_metadata_file_applies_fixture(tmp_path: Path) -> None:
    search_dir = tmp_path / "search"
    indices_dir = search_dir / "data" / "indices"
    indices_dir.mkdir(parents=True)

    fixture = Path("tests/fixtures/storage/legacy_index_metadata_missing_fields.json")
    (indices_dir / "index_metadata.json").write_text(fixture.read_text(encoding="utf-8"), encoding="utf-8")

    plan = migrate_index_metadata_file(
        search_dir,
        embedding_model="all-MiniLM-L6-v2",
        apply=True,
    )

    assert plan.has_changes is True
    payload = json.loads((indices_dir / "index_metadata.json").read_text(encoding="utf-8"))
    assert payload["embedding_model"] == "all-MiniLM-L6-v2"
    assert payload["chunk_size"] == 1500
    assert payload["chunk_overlap"] == 200
    assert payload["next_vector_id"] == 5


def test_migrate_index_metadata_root_applies_backup_dataset_fixture(tmp_path: Path) -> None:
    dataset_root = tmp_path / "legacy_backup"
    fixture = Path("tests/fixtures/storage/legacy_dataset_bundle/backups/legacy_full_dataset")
    shutil.copytree(fixture, dataset_root, dirs_exist_ok=True)

    plan = migrate_index_metadata_root(
        dataset_root,
        embedding_model="all-MiniLM-L6-v2",
        apply=True,
    )

    assert plan.has_changes is True
    payload = json.loads((dataset_root / "data" / "indices" / "index_metadata.json").read_text(encoding="utf-8"))
    assert payload["embedding_model"] == "all-MiniLM-L6-v2"
    assert payload["chunk_size"] == 1500
    assert payload["chunk_overlap"] == 200
    assert payload["next_vector_id"] == 4


def test_plan_backup_metadata_migration_marks_missing_version_repairable() -> None:
    payload = {
        "timestamp": "20260316_120000",
        "backup_path": "/tmp/backup",
        "source_path": "/tmp/search",
        "file_count": 1,
        "total_size_bytes": 5,
        "total_size_mb": 0.0,
        "backup_type": "manual",
    }

    plan = plan_backup_metadata_migration(payload)

    assert plan.has_changes is True
    assert plan.changed_fields == ("metadata_version",)
    assert plan.migrated_payload["metadata_version"] == 1


def test_plan_backup_manifest_migration_marks_missing_version_repairable() -> None:
    payload = {
        "backup_mode": "full",
        "encrypted": False,
        "created_at": "2026-03-16T12:00:00",
        "parent_name": None,
        "files": {},
        "deleted_files": [],
    }

    plan = plan_backup_manifest_migration(payload)

    assert plan.has_changes is True
    assert plan.changed_fields == ("manifest_version",)
    assert plan.migrated_payload["manifest_version"] == 1


def test_migrate_backup_manifest_repairs_fixture(tmp_path: Path) -> None:
    backup_dir = tmp_path / "repairable_manifest_base"
    fixture = Path("tests/fixtures/storage/backup_contract_bundle/backups/repairable_manifest_base")
    shutil.copytree(fixture, backup_dir, dirs_exist_ok=True)

    plan = migrate_backup_manifest(backup_dir, apply=True)

    assert plan.has_changes is True
    payload = json.loads((backup_dir / "backup_manifest.json").read_text(encoding="utf-8"))
    assert payload["manifest_version"] == 1


def test_migrate_backup_metadata_rejects_unsupported_version(tmp_path: Path) -> None:
    backup_dir = tmp_path / "mixed_version_metadata_full"
    fixture = Path("tests/fixtures/storage/backup_contract_bundle/backups/mixed_version_metadata_full")
    shutil.copytree(fixture, backup_dir, dirs_exist_ok=True)

    with pytest.raises(ValueError, match="version mismatch"):
        migrate_backup_metadata(backup_dir, apply=False)
