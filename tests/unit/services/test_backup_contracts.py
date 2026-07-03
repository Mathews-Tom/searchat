from __future__ import annotations

from pathlib import Path

from searchat.services.backup_contracts import inspect_legacy_full_backup, inspect_manifest_backup
from searchat.services.storage_contracts import BACKUP_SOURCE_SCHEMA_VERSION, BackupMetadata


def test_inspect_legacy_full_backup_without_hash_verification_is_valid(tmp_path) -> None:
    inspection = inspect_legacy_full_backup(
        "legacy_full",
        tmp_path / "legacy_full",
        structure_valid=True,
        verify_hashes=False,
    )

    assert inspection.valid is True
    assert inspection.snapshot_browsable is True
    assert inspection.has_manifest is False
    assert inspection.errors == ()


def test_inspect_legacy_full_backup_with_hash_verification_requires_manifest(tmp_path) -> None:
    inspection = inspect_legacy_full_backup(
        "legacy_full",
        tmp_path / "legacy_full",
        structure_valid=True,
        verify_hashes=True,
    )

    assert inspection.valid is False
    assert inspection.snapshot_browsable is True
    assert inspection.errors == ("Backup manifest missing",)


def test_inspect_manifest_backup_keeps_chain_contract_fields() -> None:
    inspection = inspect_manifest_backup(
        "inc_20260315",
        backup_mode="incremental",
        encrypted=False,
        parent_name="base_20260315",
        chain_length=2,
        snapshot_browsable=False,
        errors=["Backup manifest missing: base_20260315"],
    )

    assert inspection.valid is False
    assert inspection.backup_mode == "incremental"
    assert inspection.parent_name == "base_20260315"
    assert inspection.chain_length == 2
    assert inspection.errors == ("Backup manifest missing: base_20260315",)


def test_backup_metadata_roundtrips_excludes_derived_fields() -> None:
    metadata = BackupMetadata(
        timestamp="20260703_000000",
        backup_path=Path("/backups/snap_20260703_000000"),
        source_path=Path("/data"),
        file_count=3,
        total_size_bytes=1024,
        excludes_derived=True,
        derived_schema_version=BACKUP_SOURCE_SCHEMA_VERSION,
    )

    restored = BackupMetadata.from_dict(metadata.to_dict())

    assert restored.excludes_derived is True
    assert restored.derived_schema_version == BACKUP_SOURCE_SCHEMA_VERSION


def test_backup_metadata_from_dict_defaults_excludes_derived_for_legacy_payload() -> None:
    """Pre-M4 metadata JSON never wrote these keys -- from_dict must default them
    to "full-copy" values rather than raising, so old backups stay listable."""
    legacy_payload = {
        "metadata_version": 1,
        "timestamp": "20260101_000000",
        "backup_path": "/backups/legacy_20260101_000000",
        "source_path": "/data",
        "file_count": 5,
        "total_size_bytes": 2048,
        "backup_type": "manual",
    }

    restored = BackupMetadata.from_dict(legacy_payload)

    assert restored.excludes_derived is False
    assert restored.derived_schema_version == 0
