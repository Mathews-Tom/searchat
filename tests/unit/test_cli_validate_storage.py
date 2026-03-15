from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from searchat.services.backup import BackupManager


def test_validate_storage_help_text(capsys) -> None:
    from searchat.cli.validate_cmd import run_validate

    try:
        run_validate(["storage", "--help"])
    except SystemExit as exc:
        assert exc.code == 0

    captured = capsys.readouterr()
    assert "storage" in captured.out.lower()
    assert "--repair" in captured.out


def test_validate_storage_reports_repairable_issue(temp_search_dir: Path, capsys) -> None:
    from searchat.cli.validate_cmd import run_validate

    manager = BackupManager(temp_search_dir)
    live_file = temp_search_dir / "data" / "conversations" / "conv.parquet"
    live_file.parent.mkdir(parents=True, exist_ok=True)
    live_file.write_bytes(b"PAR1\n")

    backup = manager.create_backup(backup_name="legacy")
    metadata_path = backup.backup_path / manager.METADATA_FILE
    payload = json.loads(metadata_path.read_text(encoding="utf-8"))
    payload.pop("metadata_version", None)
    metadata_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    cfg = SimpleNamespace(embedding=SimpleNamespace(model="all-MiniLM-L6-v2"))
    with (
        patch("searchat.config.Config.load", return_value=cfg),
        patch("searchat.config.PathResolver.get_shared_search_dir", return_value=temp_search_dir),
    ):
        result = run_validate(["storage"])

    captured = capsys.readouterr()
    assert result == 0
    assert "backup_metadata" in captured.out
    assert "yes" in captured.out.lower()


def test_validate_storage_repair_updates_metadata(temp_search_dir: Path) -> None:
    from searchat.cli.validate_cmd import run_validate

    manager = BackupManager(temp_search_dir)
    live_file = temp_search_dir / "data" / "conversations" / "conv.parquet"
    live_file.parent.mkdir(parents=True, exist_ok=True)
    live_file.write_bytes(b"PAR1\n")

    backup = manager.create_backup(backup_name="legacy")
    metadata_path = backup.backup_path / manager.METADATA_FILE
    payload = json.loads(metadata_path.read_text(encoding="utf-8"))
    payload.pop("metadata_version", None)
    metadata_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    cfg = SimpleNamespace(embedding=SimpleNamespace(model="all-MiniLM-L6-v2"))
    with (
        patch("searchat.config.Config.load", return_value=cfg),
        patch("searchat.config.PathResolver.get_shared_search_dir", return_value=temp_search_dir),
    ):
        result = run_validate(["storage", "--repair"])

    repaired_payload = json.loads(metadata_path.read_text(encoding="utf-8"))
    assert result == 0
    assert repaired_payload["metadata_version"] == 1


def test_validate_storage_reports_index_metadata_migration(temp_search_dir: Path, capsys) -> None:
    from searchat.cli.validate_cmd import run_validate

    indices_dir = temp_search_dir / "data" / "indices"
    indices_dir.mkdir(parents=True, exist_ok=True)
    fixture = Path("tests/fixtures/storage/legacy_index_metadata_missing_fields.json")
    (indices_dir / "index_metadata.json").write_text(fixture.read_text(encoding="utf-8"), encoding="utf-8")

    cfg = SimpleNamespace(embedding=SimpleNamespace(model="all-MiniLM-L6-v2"))
    with (
        patch("searchat.config.Config.load", return_value=cfg),
        patch("searchat.config.PathResolver.get_shared_search_dir", return_value=temp_search_dir),
    ):
        result = run_validate(["storage"])

    captured = capsys.readouterr()
    assert result == 0
    assert "index_metadata" in captured.out
    assert "embedding_model" in captured.out
