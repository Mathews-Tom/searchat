"""Storage inspection and safe metadata normalization helpers."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from searchat.services.storage_contracts import (
    BACKUP_MANIFEST_FILE,
    BACKUP_METADATA_FILE,
    BackupManifest,
    BackupMetadata,
    StorageCompatibilityError,
    index_metadata_path,
)
from searchat.services.storage_migrations import migrate_index_metadata_root


@dataclass(frozen=True)
class DatasetIndexTarget:
    scope: str
    dataset_root: Path
    metadata_path: Path
    label: str


@dataclass(frozen=True)
class StorageIssue:
    severity: str
    scope: str
    path: Path
    message: str
    repairable: bool = False


@dataclass(frozen=True)
class StorageHealthReport:
    search_dir: Path
    issues: list[StorageIssue]
    repairs_applied: int = 0

    @property
    def is_healthy(self) -> bool:
        return not any(issue.severity == "error" for issue in self.issues)

    @property
    def repairable_issues(self) -> list[StorageIssue]:
        return [issue for issue in self.issues if issue.repairable]


def _iter_index_targets(search_dir: Path) -> list[DatasetIndexTarget]:
    targets = [
        DatasetIndexTarget(
            scope="index_metadata",
            dataset_root=search_dir,
            metadata_path=index_metadata_path(search_dir),
            label="live dataset",
        )
    ]

    backups_dir = search_dir / "backups"
    if not backups_dir.exists():
        return targets

    for backup_dir in sorted(path for path in backups_dir.iterdir() if path.is_dir()):
        manifest_path = backup_dir / BACKUP_MANIFEST_FILE
        if manifest_path.exists():
            try:
                manifest = BackupManifest.from_dict(json.loads(manifest_path.read_text(encoding="utf-8")))
            except StorageCompatibilityError:
                continue
            if manifest.backup_mode != "full" or manifest.encrypted:
                continue
        metadata_path = index_metadata_path(backup_dir)
        if metadata_path.exists():
            targets.append(
                DatasetIndexTarget(
                    scope="backup_index_metadata",
                    dataset_root=backup_dir,
                    metadata_path=metadata_path,
                    label=f"backup dataset '{backup_dir.name}'",
                )
            )

    return targets


def _inspect_index_target(
    target: DatasetIndexTarget,
    *,
    embedding_model: str | None,
) -> StorageIssue | None:
    if not target.metadata_path.exists():
        return None
    try:
        plan = migrate_index_metadata_root(
            target.dataset_root,
            embedding_model=embedding_model,
            apply=False,
        )
        plan.migrated.validate_compatible(embedding_model=embedding_model)
        if plan.has_changes:
            return StorageIssue(
                severity="warning",
                scope=target.scope,
                path=target.metadata_path,
                message=(
                    f"{target.label.capitalize()} index metadata can be migrated by normalizing fields: "
                    + ", ".join(plan.changed_fields)
                ),
                repairable=True,
            )
    except (FileNotFoundError, StorageCompatibilityError) as exc:
        return StorageIssue(
            severity="error",
            scope=target.scope,
            path=target.metadata_path,
            message=str(exc),
        )
    return None


def inspect_storage_health(
    search_dir: Path,
    *,
    embedding_model: str | None = None,
) -> StorageHealthReport:
    issues: list[StorageIssue] = []
    for target in _iter_index_targets(search_dir):
        issue = _inspect_index_target(target, embedding_model=embedding_model)
        if issue is not None:
            issues.append(issue)

    backups_dir = search_dir / "backups"
    if backups_dir.exists():
        for backup_dir in sorted(path for path in backups_dir.iterdir() if path.is_dir()):
            metadata_path = backup_dir / BACKUP_METADATA_FILE
            if metadata_path.exists():
                try:
                    payload = json.loads(metadata_path.read_text(encoding="utf-8"))
                    metadata = BackupMetadata.from_dict(payload)
                    normalized = metadata.normalized()
                    if "metadata_version" not in payload or normalized != metadata:
                        issues.append(
                            StorageIssue(
                                severity="warning",
                                scope="backup_metadata",
                                path=metadata_path,
                                message="Backup metadata can be normalized to the current contract version.",
                                repairable=True,
                            )
                        )
                except StorageCompatibilityError as exc:
                    issues.append(
                        StorageIssue(
                            severity="error",
                            scope="backup_metadata",
                            path=metadata_path,
                            message=str(exc),
                        )
                    )
            manifest_path = backup_dir / BACKUP_MANIFEST_FILE
            if manifest_path.exists():
                try:
                    BackupManifest.from_dict(json.loads(manifest_path.read_text(encoding="utf-8")))
                except StorageCompatibilityError as exc:
                    issues.append(
                        StorageIssue(
                            severity="error",
                            scope="backup_manifest",
                            path=manifest_path,
                            message=str(exc),
                        )
                    )

    return StorageHealthReport(search_dir=search_dir, issues=issues)


def repair_storage_metadata(
    search_dir: Path,
    *,
    embedding_model: str | None = None,
) -> StorageHealthReport:
    repairs_applied = 0

    for target in _iter_index_targets(search_dir):
        try:
            plan = migrate_index_metadata_root(
                target.dataset_root,
                embedding_model=embedding_model,
                apply=True,
            )
            if plan.has_changes:
                repairs_applied += 1
        except (FileNotFoundError, StorageCompatibilityError):
            pass

    backups_dir = search_dir / "backups"
    if backups_dir.exists():
        for backup_dir in sorted(path for path in backups_dir.iterdir() if path.is_dir()):
            metadata_path = backup_dir / BACKUP_METADATA_FILE
            if not metadata_path.exists():
                continue
            payload = json.loads(metadata_path.read_text(encoding="utf-8"))
            metadata = BackupMetadata.from_dict(payload)
            normalized = metadata.normalized()
            normalized_payload = normalized.to_dict()
            payload_changed = any(payload.get(key) != value for key, value in normalized_payload.items())
            if payload_changed:
                metadata_path.write_text(json.dumps(normalized_payload, indent=2), encoding="utf-8")
                repairs_applied += 1

    refreshed = inspect_storage_health(search_dir, embedding_model=embedding_model)
    return StorageHealthReport(
        search_dir=search_dir,
        issues=refreshed.issues,
        repairs_applied=repairs_applied,
    )
