"""Migration helpers for persisted storage metadata."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from searchat.config.constants import INDEX_METADATA_FILENAME
from searchat.services.storage_contracts import (
    BACKUP_MANIFEST_FILE,
    BACKUP_MANIFEST_VERSION,
    BACKUP_METADATA_FILE,
    BACKUP_METADATA_VERSION,
    BackupManifest,
    BackupMetadata,
    StorageCompatibilityError,
    IndexMetadata,
    index_metadata_path,
    read_index_metadata,
    read_index_metadata_root,
    write_index_metadata,
    write_index_metadata_root,
)


@dataclass(frozen=True)
class MetadataMigrationPlan:
    original: IndexMetadata
    migrated: IndexMetadata
    changed_fields: tuple[str, ...]

    @property
    def has_changes(self) -> bool:
        return bool(self.changed_fields)


@dataclass(frozen=True)
class BackupMetadataMigrationPlan:
    original_payload: dict
    migrated_payload: dict
    changed_fields: tuple[str, ...]

    @property
    def has_changes(self) -> bool:
        return bool(self.changed_fields)


@dataclass(frozen=True)
class BackupManifestMigrationPlan:
    original_payload: dict
    migrated_payload: dict
    changed_fields: tuple[str, ...]

    @property
    def has_changes(self) -> bool:
        return bool(self.changed_fields)


def plan_index_metadata_migration(
    metadata: IndexMetadata,
    *,
    embedding_model: str | None = None,
) -> MetadataMigrationPlan:
    migrated = metadata.normalized(embedding_model=embedding_model)
    changed = tuple(
        field
        for field in metadata.to_dict().keys()
        if metadata.to_dict().get(field) != migrated.to_dict().get(field)
    )
    return MetadataMigrationPlan(original=metadata, migrated=migrated, changed_fields=changed)


def read_raw_index_metadata(dataset_root: Path) -> dict:
    metadata_path = index_metadata_path(dataset_root)
    with open(metadata_path, "r", encoding="utf-8") as f:
        return json.load(f)


def read_raw_backup_metadata(backup_dir: Path) -> dict:
    with open(backup_dir / BACKUP_METADATA_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def read_raw_backup_manifest(backup_dir: Path) -> dict:
    with open(backup_dir / BACKUP_MANIFEST_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def plan_backup_metadata_migration(payload: dict) -> BackupMetadataMigrationPlan:
    version = payload.get("metadata_version")
    if version not in (None, BACKUP_METADATA_VERSION):
        raise StorageCompatibilityError(
            f"Backup metadata version mismatch: artifact uses version {int(version)}, "
            f"expected version {BACKUP_METADATA_VERSION}."
        )
    metadata = BackupMetadata.from_dict(payload)
    migrated_payload = metadata.normalized().to_dict()
    changed = tuple(
        key
        for key in migrated_payload.keys()
        if payload.get(key) != migrated_payload.get(key)
    )
    return BackupMetadataMigrationPlan(
        original_payload=dict(payload),
        migrated_payload=migrated_payload,
        changed_fields=changed,
    )


def plan_backup_manifest_migration(payload: dict) -> BackupManifestMigrationPlan:
    version = payload.get("manifest_version")
    if version not in (None, BACKUP_MANIFEST_VERSION):
        raise StorageCompatibilityError(
            f"Backup manifest version mismatch: artifact uses version {int(version)}, "
            f"expected version {BACKUP_MANIFEST_VERSION}."
        )
    manifest = BackupManifest.from_dict(payload)
    migrated_payload = manifest.to_dict()
    changed = tuple(
        key
        for key in migrated_payload.keys()
        if payload.get(key) != migrated_payload.get(key)
    )
    return BackupManifestMigrationPlan(
        original_payload=dict(payload),
        migrated_payload=migrated_payload,
        changed_fields=changed,
    )


def migrate_index_metadata_root(
    dataset_root: Path,
    *,
    embedding_model: str | None = None,
    apply: bool = False,
) -> MetadataMigrationPlan:
    metadata = read_index_metadata_root(dataset_root)
    plan = plan_index_metadata_migration(metadata, embedding_model=embedding_model)
    if apply and plan.has_changes:
        write_index_metadata_root(dataset_root, plan.migrated)
    return plan


def migrate_backup_metadata(
    backup_dir: Path,
    *,
    apply: bool = False,
) -> BackupMetadataMigrationPlan:
    payload = read_raw_backup_metadata(backup_dir)
    plan = plan_backup_metadata_migration(payload)
    if apply and plan.has_changes:
        (backup_dir / BACKUP_METADATA_FILE).write_text(
            json.dumps(plan.migrated_payload, indent=2),
            encoding="utf-8",
        )
    return plan


def migrate_backup_manifest(
    backup_dir: Path,
    *,
    apply: bool = False,
) -> BackupManifestMigrationPlan:
    payload = read_raw_backup_manifest(backup_dir)
    plan = plan_backup_manifest_migration(payload)
    if apply and plan.has_changes:
        (backup_dir / BACKUP_MANIFEST_FILE).write_text(
            json.dumps(plan.migrated_payload, indent=2),
            encoding="utf-8",
        )
    return plan


def migrate_index_metadata_file(
    search_dir: Path,
    *,
    embedding_model: str | None = None,
    apply: bool = False,
) -> MetadataMigrationPlan:
    metadata = read_index_metadata(search_dir)
    plan = plan_index_metadata_migration(metadata, embedding_model=embedding_model)
    if apply and plan.has_changes:
        write_index_metadata(search_dir, plan.migrated)
    return plan
