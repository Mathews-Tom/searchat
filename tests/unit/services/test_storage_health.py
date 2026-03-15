from __future__ import annotations

import json
import shutil
from pathlib import Path

from searchat.services.backup import BackupManager
from searchat.services.storage_contracts import BACKUP_MANIFEST_FILE
from searchat.services.storage_health import inspect_storage_health, repair_storage_metadata


def test_inspect_storage_health_flags_repairable_legacy_backup_metadata(temp_search_dir: Path) -> None:
    manager = BackupManager(temp_search_dir)
    live_file = temp_search_dir / "data" / "conversations" / "conv.parquet"
    live_file.parent.mkdir(parents=True, exist_ok=True)
    live_file.write_bytes(b"PAR1\n")

    backup = manager.create_backup(backup_name="legacy")
    metadata_path = backup.backup_path / manager.METADATA_FILE
    payload = json.loads(metadata_path.read_text(encoding="utf-8"))
    payload.pop("metadata_version", None)
    metadata_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    report = inspect_storage_health(temp_search_dir)

    assert any(issue.scope == "backup_metadata" and issue.repairable for issue in report.issues)


def test_repair_storage_metadata_normalizes_legacy_backup_metadata(temp_search_dir: Path) -> None:
    manager = BackupManager(temp_search_dir)
    live_file = temp_search_dir / "data" / "conversations" / "conv.parquet"
    live_file.parent.mkdir(parents=True, exist_ok=True)
    live_file.write_bytes(b"PAR1\n")

    backup = manager.create_backup(backup_name="legacy")
    metadata_path = backup.backup_path / manager.METADATA_FILE
    payload = json.loads(metadata_path.read_text(encoding="utf-8"))
    payload.pop("metadata_version", None)
    metadata_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    report = repair_storage_metadata(temp_search_dir)

    assert report.repairs_applied == 1
    repaired_payload = json.loads(metadata_path.read_text(encoding="utf-8"))
    assert repaired_payload["metadata_version"] == 1


def test_inspect_storage_health_flags_legacy_backup_dataset_index_metadata(temp_search_dir: Path) -> None:
    fixture = Path("tests/fixtures/storage/legacy_dataset_bundle")
    shutil.copytree(fixture, temp_search_dir, dirs_exist_ok=True)

    report = inspect_storage_health(temp_search_dir, embedding_model="all-MiniLM-L6-v2")

    assert any(issue.scope == "backup_index_metadata" and issue.repairable for issue in report.issues)


def test_repair_storage_metadata_migrates_legacy_dataset_bundle(temp_search_dir: Path) -> None:
    fixture = Path("tests/fixtures/storage/legacy_dataset_bundle")
    shutil.copytree(fixture, temp_search_dir, dirs_exist_ok=True)

    report = repair_storage_metadata(temp_search_dir, embedding_model="all-MiniLM-L6-v2")

    assert report.repairs_applied == 3

    live_payload = json.loads(
        (temp_search_dir / "data" / "indices" / "index_metadata.json").read_text(encoding="utf-8")
    )
    backup_payload = json.loads(
        (
            temp_search_dir
            / "backups"
            / "legacy_full_dataset"
            / "data"
            / "indices"
            / "index_metadata.json"
        ).read_text(encoding="utf-8")
    )
    backup_meta = json.loads(
        (temp_search_dir / "backups" / "legacy_full_dataset" / "backup_metadata.json").read_text(encoding="utf-8")
    )

    assert live_payload["embedding_model"] == "all-MiniLM-L6-v2"
    assert live_payload["next_vector_id"] == 3
    assert backup_payload["embedding_model"] == "all-MiniLM-L6-v2"
    assert backup_payload["next_vector_id"] == 4
    assert backup_meta["metadata_version"] == 1


def test_inspect_storage_health_flags_broken_backup_chain(temp_search_dir: Path) -> None:
    manager = BackupManager(temp_search_dir)
    live_file = temp_search_dir / "data" / "conversations" / "conv.parquet"
    settings = temp_search_dir / "config" / "settings.toml"
    live_file.parent.mkdir(parents=True, exist_ok=True)
    settings.parent.mkdir(parents=True, exist_ok=True)
    live_file.write_bytes(b"PAR1\n")
    settings.write_bytes(b"a = 1\n")

    base = manager.create_backup(backup_name="base")
    settings.write_bytes(b"a = 2\n")
    child = manager.create_incremental_backup(parent_name=base.backup_path.name, backup_name="child")
    (base.backup_path / BACKUP_MANIFEST_FILE).unlink()

    report = inspect_storage_health(temp_search_dir)

    assert any(
        issue.scope == "backup_chain"
        and child.backup_path.name in issue.message
        and issue.severity == "error"
        for issue in report.issues
    )


def test_inspect_storage_health_flags_fixture_backup_contract_bundle(temp_search_dir: Path) -> None:
    fixture = Path("tests/fixtures/storage/backup_contract_bundle")
    shutil.copytree(fixture, temp_search_dir, dirs_exist_ok=True)

    report = inspect_storage_health(temp_search_dir)

    assert any(
        issue.scope == "backup_manifest"
        and issue.path.name == BACKUP_MANIFEST_FILE
        and "version mismatch" in issue.message.lower()
        for issue in report.issues
    )
    assert any(
        issue.scope == "backup_chain"
        and issue.path.name == "broken_chain_child"
        and "validation failed" in issue.message.lower()
        for issue in report.issues
    )
