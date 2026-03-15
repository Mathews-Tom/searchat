from __future__ import annotations

from searchat.services.backup_contracts import inspect_legacy_full_backup, inspect_manifest_backup


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
