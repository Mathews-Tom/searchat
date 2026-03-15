from __future__ import annotations

import json
from pathlib import Path

from searchat.services.backup import BackupManager
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
