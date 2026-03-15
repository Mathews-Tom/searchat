"""Typed inspection helpers for backup artifacts and snapshot eligibility."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class BackupArtifactInspection:
    backup_name: str
    backup_mode: str
    encrypted: bool
    parent_name: str | None
    chain_length: int
    snapshot_browsable: bool
    has_manifest: bool
    valid: bool
    errors: tuple[str, ...]

    def to_dict(self) -> dict[str, object]:
        return {
            "backup_name": self.backup_name,
            "backup_mode": self.backup_mode,
            "encrypted": self.encrypted,
            "parent_name": self.parent_name,
            "chain_length": self.chain_length,
            "snapshot_browsable": self.snapshot_browsable,
            "has_manifest": self.has_manifest,
            "valid": self.valid,
            "errors": list(self.errors),
        }


def inspect_legacy_full_backup(
    backup_name: str,
    backup_path: Path,
    *,
    structure_valid: bool,
    verify_hashes: bool,
) -> BackupArtifactInspection:
    errors: list[str] = []
    if verify_hashes:
        errors.append("Backup manifest missing")
    return BackupArtifactInspection(
        backup_name=backup_name,
        backup_mode="full",
        encrypted=False,
        parent_name=None,
        chain_length=1,
        snapshot_browsable=structure_valid,
        has_manifest=False,
        valid=structure_valid and not errors,
        errors=tuple(errors),
    )


def inspect_manifest_backup(
    backup_name: str,
    *,
    backup_mode: str,
    encrypted: bool,
    parent_name: str | None,
    chain_length: int,
    snapshot_browsable: bool,
    errors: list[str],
) -> BackupArtifactInspection:
    return BackupArtifactInspection(
        backup_name=backup_name,
        backup_mode=backup_mode,
        encrypted=encrypted,
        parent_name=parent_name,
        chain_length=chain_length,
        snapshot_browsable=snapshot_browsable,
        has_manifest=True,
        valid=not errors,
        errors=tuple(errors),
    )
