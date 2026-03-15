from __future__ import annotations

import json
import shutil
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq

from searchat.config import Config
from searchat.config.constants import INDEX_FORMAT, INDEX_FORMAT_VERSION, INDEX_SCHEMA_VERSION
from searchat.core.search_engine import SearchEngine
from searchat.models import CONVERSATION_SCHEMA
from searchat.services.backup import BackupManager
from searchat.services.storage_contracts import (
    BACKUP_MANIFEST_FILE,
    IndexMetadata,
    write_index_metadata,
)


def _write_empty_conversation_parquet(path: Path) -> None:
    table = pa.Table.from_pylist([], schema=CONVERSATION_SCHEMA)
    pq.write_table(table, path)


def test_storage_compatibility_current_index_metadata_is_loadable(tmp_path: Path) -> None:
    search_dir = tmp_path / "search"
    conversations_dir = search_dir / "data" / "conversations"
    indices_dir = search_dir / "data" / "indices"
    conversations_dir.mkdir(parents=True)
    indices_dir.mkdir(parents=True)

    _write_empty_conversation_parquet(conversations_dir / "project_test.parquet")
    (indices_dir / "embeddings.metadata.parquet").write_bytes(b"PAR1")

    metadata = IndexMetadata(
        schema_version=INDEX_SCHEMA_VERSION,
        index_format_version=INDEX_FORMAT_VERSION,
        created_at="2026-03-15T00:00:00",
        embedding_model=Config.load().embedding.model,
        format=INDEX_FORMAT,
        last_updated="2026-03-15T00:00:00",
        total_conversations=0,
        total_chunks=0,
        next_vector_id=0,
    )
    write_index_metadata(search_dir, metadata)

    engine = SearchEngine(search_dir, Config.load())
    engine._validate_index_metadata()


def test_storage_compatibility_legacy_backup_metadata_remains_listable(temp_search_dir: Path) -> None:
    manager = BackupManager(temp_search_dir)
    live_file = temp_search_dir / "data" / "conversations" / "conv.parquet"
    live_file.parent.mkdir(parents=True, exist_ok=True)
    live_file.write_bytes(b"PAR1\n")

    backup = manager.create_backup(backup_name="compat")
    metadata_path = backup.backup_path / manager.METADATA_FILE
    payload = json.loads(metadata_path.read_text(encoding="utf-8"))
    payload.pop("metadata_version", None)
    metadata_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    listed = manager.list_backups()
    assert listed
    assert listed[0].backup_path == backup.backup_path


def test_storage_compatibility_invalid_manifest_version_fails_closed(temp_search_dir: Path) -> None:
    manager = BackupManager(temp_search_dir)
    live_file = temp_search_dir / "data" / "conversations" / "conv.parquet"
    live_file.parent.mkdir(parents=True, exist_ok=True)
    live_file.write_bytes(b"PAR1\n")

    backup = manager.create_backup(backup_name="invalid-manifest")
    manifest_path = backup.backup_path / BACKUP_MANIFEST_FILE
    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    payload["manifest_version"] = 999
    manifest_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    result = manager.validate_backup_artifact(backup.backup_path.name, verify_hashes=False)
    assert result["valid"] is False
    assert any("manifest version mismatch" in error for error in result["errors"])


def test_storage_compatibility_repair_normalizes_legacy_backup_metadata(temp_search_dir: Path) -> None:
    from searchat.services.storage_health import inspect_storage_health, repair_storage_metadata

    manager = BackupManager(temp_search_dir)
    live_file = temp_search_dir / "data" / "conversations" / "conv.parquet"
    live_file.parent.mkdir(parents=True, exist_ok=True)
    live_file.write_bytes(b"PAR1\n")

    backup = manager.create_backup(backup_name="repairable")
    metadata_path = backup.backup_path / manager.METADATA_FILE
    payload = json.loads(metadata_path.read_text(encoding="utf-8"))
    payload.pop("metadata_version", None)
    metadata_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    before = inspect_storage_health(temp_search_dir)
    assert any(issue.scope == "backup_metadata" and issue.repairable for issue in before.issues)

    repaired = repair_storage_metadata(temp_search_dir)
    assert repaired.repairs_applied == 1
    assert not repaired.issues


def test_storage_compatibility_repair_migrates_legacy_index_metadata(temp_search_dir: Path) -> None:
    from searchat.services.storage_health import inspect_storage_health, repair_storage_metadata

    indices_dir = temp_search_dir / "data" / "indices"
    indices_dir.mkdir(parents=True, exist_ok=True)
    fixture = Path("tests/fixtures/storage/legacy_index_metadata_missing_fields.json")
    metadata_path = indices_dir / "index_metadata.json"
    metadata_path.write_text(fixture.read_text(encoding="utf-8"), encoding="utf-8")

    before = inspect_storage_health(temp_search_dir, embedding_model="all-MiniLM-L6-v2")
    assert any(issue.scope == "index_metadata" and issue.repairable for issue in before.issues)

    repaired = repair_storage_metadata(temp_search_dir, embedding_model="all-MiniLM-L6-v2")
    assert repaired.repairs_applied == 1

    payload = json.loads(metadata_path.read_text(encoding="utf-8"))
    assert payload["embedding_model"] == "all-MiniLM-L6-v2"
    assert payload["chunk_size"] == 1500
    assert payload["chunk_overlap"] == 200
    assert payload["next_vector_id"] == 5


def test_storage_compatibility_repair_migrates_legacy_dataset_bundle(temp_search_dir: Path) -> None:
    from searchat.services.storage_health import inspect_storage_health, repair_storage_metadata

    fixture = Path("tests/fixtures/storage/legacy_dataset_bundle")
    shutil.copytree(fixture, temp_search_dir, dirs_exist_ok=True)

    before = inspect_storage_health(temp_search_dir, embedding_model="all-MiniLM-L6-v2")
    repairable_scopes = {issue.scope for issue in before.issues if issue.repairable}
    assert {"index_metadata", "backup_index_metadata", "backup_metadata"} <= repairable_scopes

    repaired = repair_storage_metadata(temp_search_dir, embedding_model="all-MiniLM-L6-v2")
    assert repaired.repairs_applied == 3
    assert not repaired.issues

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
    assert live_payload["chunk_size"] == 1500
    assert backup_payload["embedding_model"] == "all-MiniLM-L6-v2"
    assert backup_payload["next_vector_id"] == 4
    assert backup_meta["metadata_version"] == 1


def test_storage_compatibility_legacy_full_backup_without_manifest_remains_browsable(temp_search_dir: Path) -> None:
    manager = BackupManager(temp_search_dir)
    live_file = temp_search_dir / "data" / "conversations" / "conv.parquet"
    live_file.parent.mkdir(parents=True, exist_ok=True)
    live_file.write_bytes(b"PAR1\n")

    backup = manager.create_backup(backup_name="legacy-full")
    (backup.backup_path / BACKUP_MANIFEST_FILE).unlink()

    result = manager.validate_backup_artifact(backup.backup_path.name, verify_hashes=False)
    assert result["valid"] is True
    assert result["has_manifest"] is False
    assert result["snapshot_browsable"] is True
    assert result["chain_length"] == 1


def test_storage_compatibility_invalid_chain_with_missing_parent_manifest_fails_closed(temp_search_dir: Path) -> None:
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

    result = manager.validate_backup_artifact(child.backup_path.name, verify_hashes=False)
    assert result["valid"] is False
    assert result["snapshot_browsable"] is False
    assert any("Backup manifest missing" in error for error in result["errors"])


def test_storage_compatibility_storage_health_reports_broken_backup_chain(temp_search_dir: Path) -> None:
    from searchat.services.storage_health import inspect_storage_health

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
        and issue.path == child.backup_path
        and "validation failed" in issue.message.lower()
        for issue in report.issues
    )
