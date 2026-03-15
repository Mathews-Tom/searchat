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
    IndexMetadata,
    StorageCompatibilityError,
    read_index_metadata,
    write_index_metadata,
)


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


def inspect_storage_health(
    search_dir: Path,
    *,
    embedding_model: str | None = None,
) -> StorageHealthReport:
    issues: list[StorageIssue] = []
    indices_dir = search_dir / "data" / "indices"
    metadata_path = indices_dir / "index_metadata.json"

    if metadata_path.exists():
        try:
            index_metadata = read_index_metadata(search_dir)
            index_metadata.validate_compatible(embedding_model=embedding_model)
            normalized = index_metadata.normalized(embedding_model=embedding_model)
            if normalized != index_metadata:
                issues.append(
                    StorageIssue(
                        severity="warning",
                        scope="index_metadata",
                        path=metadata_path,
                        message="Index metadata is missing normalizable fields.",
                        repairable=True,
                    )
                )
        except FileNotFoundError:
            pass
        except StorageCompatibilityError as exc:
            issues.append(
                StorageIssue(
                    severity="error",
                    scope="index_metadata",
                    path=metadata_path,
                    message=str(exc),
                )
            )

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
    report = inspect_storage_health(search_dir, embedding_model=embedding_model)

    indices_dir = search_dir / "data" / "indices"
    metadata_path = indices_dir / "index_metadata.json"
    if metadata_path.exists():
        try:
            index_metadata = read_index_metadata(search_dir)
            normalized = index_metadata.normalized(embedding_model=embedding_model)
            if normalized != index_metadata:
                write_index_metadata(search_dir, normalized)
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
