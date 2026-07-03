from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

from searchat.services.backup import BackupManager


def _write_bytes(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)


@pytest.mark.unit
def test_incremental_backup_materialize_roundtrip(tmp_path: Path, temp_search_dir: Path):
    live = temp_search_dir
    mgr = BackupManager(live)

    parquet = live / "data" / "conversations" / "conv.parquet"
    settings = live / "config" / "settings.toml"
    removed = live / "data" / "code" / "removed.bin"
    added = live / "data" / "code" / "added.bin"

    _write_bytes(parquet, b"PAR1\n")
    _write_bytes(settings, b"a = 1\n")
    _write_bytes(removed, b"old\n")

    base_meta = mgr.create_backup(backup_name="base")
    base_name = base_meta.backup_path.name

    # Mutate live dataset.
    _write_bytes(settings, b"a = 2\n")
    removed.unlink()
    _write_bytes(added, b"new\n")

    inc_meta = mgr.create_incremental_backup(parent_name=base_name, backup_name="inc")
    inc_name = inc_meta.backup_path.name

    out = tmp_path / "materialized"
    mgr.materialize_backup(backup_name=inc_name, dest_dir=out, verify_hashes=True)

    assert (out / "config" / "settings.toml").read_bytes() == b"a = 2\n"
    assert not (out / "data" / "code" / "removed.bin").exists()
    assert (out / "data" / "code" / "added.bin").read_bytes() == b"new\n"
    assert (out / "data" / "conversations" / "conv.parquet").read_bytes() == b"PAR1\n"

    assert mgr.resolve_backup_chain(inc_name) == [base_name, inc_name]


@pytest.mark.unit
def test_incremental_backup_chain_length_enforced(temp_search_dir: Path):
    live = temp_search_dir
    mgr = BackupManager(live)

    _write_bytes(live / "data" / "conversations" / "conv.parquet", b"PAR1\n")
    settings = live / "config" / "settings.toml"
    _write_bytes(settings, b"a = 0\n")

    base_meta = mgr.create_backup(backup_name="base")
    parent = base_meta.backup_path.name

    # Max chain length is 10 total entries: 1 full + 9 incrementals.
    for i in range(1, 10):
        _write_bytes(settings, f"a = {i}\n".encode("ascii"))
        inc_meta = mgr.create_incremental_backup(parent_name=parent, backup_name=f"inc{i}")
        parent = inc_meta.backup_path.name
        assert len(mgr.resolve_backup_chain(parent)) == i + 1

    _write_bytes(settings, b"a = 10\n")
    with pytest.raises(ValueError, match="chain length"):
        mgr.create_incremental_backup(parent_name=parent, backup_name="inc10")


@pytest.mark.unit
def test_restore_from_incremental_backup(temp_search_dir: Path):
    live = temp_search_dir
    mgr = BackupManager(live)

    _write_bytes(live / "data" / "conversations" / "conv.parquet", b"PAR1\n")
    settings = live / "config" / "settings.toml"
    removed = live / "data" / "code" / "removed.bin"
    _write_bytes(settings, b"a = 1\n")
    _write_bytes(removed, b"old\n")

    base_meta = mgr.create_backup(backup_name="base")
    base_name = base_meta.backup_path.name

    # Define the target state we want to restore.
    _write_bytes(settings, b"a = 2\n")
    removed.unlink()
    inc_meta = mgr.create_incremental_backup(parent_name=base_name, backup_name="inc")
    inc_path = inc_meta.backup_path

    # Break the live dataset, then restore from incremental.
    _write_bytes(settings, b"a = 999\n")
    _write_bytes(removed, b"wrong\n")

    mgr.restore_from_backup(backup_path=inc_path, create_pre_restore_backup=False)

    assert settings.read_bytes() == b"a = 2\n"
    assert not removed.exists()


@pytest.mark.unit
def test_validate_backup_artifact_detects_tamper(temp_search_dir: Path):
    live = temp_search_dir
    mgr = BackupManager(live)

    parquet = live / "data" / "conversations" / "conv.parquet"
    _write_bytes(parquet, b"PAR1\n")
    meta = mgr.create_backup(backup_name="base", compressed=False)
    name = meta.backup_path.name

    # Tamper with a copied file in the backup.
    tamper = meta.backup_path / "data" / "conversations" / "conv.parquet"
    _write_bytes(tamper, b"PAR1\nTAMPER")

    res = mgr.validate_backup_artifact(name, verify_hashes=True)
    assert res["valid"] is False
    assert any("Hash mismatch" in e for e in res.get("errors", []))


@pytest.mark.unit
def test_validate_backup_artifact_legacy_full_backup_remains_snapshot_browsable(temp_search_dir: Path):
    live = temp_search_dir
    mgr = BackupManager(live)

    parquet = live / "data" / "conversations" / "conv.parquet"
    _write_bytes(parquet, b"PAR1\n")

    meta = mgr.create_backup(backup_name="legacy", compressed=False)
    backup_path = meta.backup_path
    (backup_path / "backup_manifest.json").unlink()

    res = mgr.validate_backup_artifact(backup_path.name, verify_hashes=False)
    assert res["valid"] is True
    assert res["has_manifest"] is False
    assert res["snapshot_browsable"] is True
    assert res["chain_length"] == 1


@pytest.mark.unit
def test_validate_backup_artifact_fails_closed_when_parent_manifest_is_missing(temp_search_dir: Path):
    live = temp_search_dir
    mgr = BackupManager(live)

    parquet = live / "data" / "conversations" / "conv.parquet"
    settings = live / "config" / "settings.toml"
    _write_bytes(parquet, b"PAR1\n")
    _write_bytes(settings, b"a = 1\n")

    base_meta = mgr.create_backup(backup_name="base")
    base_name = base_meta.backup_path.name

    _write_bytes(settings, b"a = 2\n")
    inc_meta = mgr.create_incremental_backup(parent_name=base_name, backup_name="inc")
    (base_meta.backup_path / "backup_manifest.json").unlink()

    res = mgr.validate_backup_artifact(inc_meta.backup_path.name, verify_hashes=False)
    assert res["valid"] is False
    assert res["snapshot_browsable"] is False
    assert any("Backup manifest missing" in e for e in res.get("errors", []))


@pytest.mark.unit
def test_get_backup_summary_legacy_full_backup_reports_valid_and_browsable(temp_search_dir: Path):
    live = temp_search_dir
    mgr = BackupManager(live)

    parquet = live / "data" / "conversations" / "conv.parquet"
    _write_bytes(parquet, b"PAR1\n")

    meta = mgr.create_backup(backup_name="legacy", compressed=False)
    (meta.backup_path / "backup_manifest.json").unlink()

    summary = mgr.get_backup_summary(meta.backup_path.name)
    assert summary["has_manifest"] is False
    assert summary["valid"] is True
    assert summary["snapshot_browsable"] is True
    assert summary["errors"] == []


@pytest.mark.unit
def test_get_backup_summary_invalid_manifest_fails_closed(temp_search_dir: Path):
    live = temp_search_dir
    mgr = BackupManager(live)

    parquet = live / "data" / "conversations" / "conv.parquet"
    _write_bytes(parquet, b"PAR1\n")

    meta = mgr.create_backup(backup_name="broken")
    manifest_path = meta.backup_path / "backup_manifest.json"
    manifest_path.write_text('{"manifest_version": 999}', encoding="utf-8")

    summary = mgr.get_backup_summary(meta.backup_path.name)
    assert summary["has_manifest"] is True
    assert summary["valid"] is False
    assert summary["snapshot_browsable"] is False
    assert summary["backup_mode"] == "unknown"
    assert summary["errors"]


@pytest.mark.unit
def test_get_backup_summary_broken_chain_uses_artifact_validation(temp_search_dir: Path):
    live = temp_search_dir
    mgr = BackupManager(live)

    parquet = live / "data" / "conversations" / "conv.parquet"
    settings = live / "config" / "settings.toml"
    _write_bytes(parquet, b"PAR1\n")
    _write_bytes(settings, b"a = 1\n")

    base = mgr.create_backup(backup_name="base")
    _write_bytes(settings, b"a = 2\n")
    child = mgr.create_incremental_backup(parent_name=base.backup_path.name, backup_name="child")
    (base.backup_path / "backup_manifest.json").unlink()

    summary = mgr.get_backup_summary(child.backup_path.name)
    assert summary["has_manifest"] is True
    assert summary["valid"] is False
    assert summary["snapshot_browsable"] is False
    assert summary["backup_mode"] == "incremental"
    assert summary["chain_length"] == 2
    assert any("Backup manifest missing" in error for error in summary["errors"])


@pytest.mark.unit
def test_inspect_backup_chain_broken_chain_preserves_topology(temp_search_dir: Path):
    live = temp_search_dir
    mgr = BackupManager(live)

    parquet = live / "data" / "conversations" / "conv.parquet"
    settings = live / "config" / "settings.toml"
    _write_bytes(parquet, b"PAR1\n")
    _write_bytes(settings, b"a = 1\n")

    base = mgr.create_backup(backup_name="base")
    _write_bytes(settings, b"a = 2\n")
    child = mgr.create_incremental_backup(parent_name=base.backup_path.name, backup_name="child")
    (base.backup_path / "backup_manifest.json").unlink()

    inspection = mgr.inspect_backup_chain(child.backup_path.name)
    assert inspection["chain"] == [base.backup_path.name, child.backup_path.name]
    assert inspection["chain_length"] == 2
    assert inspection["valid"] is False
    assert any("Backup manifest missing" in error for error in inspection["errors"])


@pytest.mark.unit
def test_list_backups_falls_back_for_mixed_version_metadata_fixture(temp_search_dir: Path):
    fixture = Path("tests/fixtures/storage/backup_contract_bundle")
    shutil.copytree(fixture, temp_search_dir, dirs_exist_ok=True)

    mgr = BackupManager(temp_search_dir)
    listed = {meta.backup_path.name: meta for meta in mgr.list_backups()}

    assert "mixed_version_metadata_full" in listed
    mixed = listed["mixed_version_metadata_full"]
    assert mixed.backup_type == "unknown"
    assert mixed.file_count >= 1


@pytest.mark.unit
def test_materialize_backup_accepts_repairable_legacy_manifest_chain_fixture(tmp_path: Path, temp_search_dir: Path):
    fixture = Path("tests/fixtures/storage/backup_contract_bundle")
    shutil.copytree(fixture, temp_search_dir, dirs_exist_ok=True)

    mgr = BackupManager(temp_search_dir)
    out = tmp_path / "materialized"
    mgr.materialize_backup(
        backup_name="repairable_manifest_child",
        dest_dir=out,
        verify_hashes=False,
    )

    assert (out / "data" / "conversations" / "conv.parquet").read_bytes().replace(b"\r\n", b"\n") == b"PAR1\n"
    assert (out / "config" / "settings.toml").read_bytes().replace(b"\r\n", b"\n") == b"a = 3\n"


@pytest.mark.unit
def test_materialize_backup_invalid_manifest_fixture_fails_closed(tmp_path: Path, temp_search_dir: Path):
    fixture = Path("tests/fixtures/storage/backup_contract_bundle")
    shutil.copytree(fixture, temp_search_dir, dirs_exist_ok=True)

    mgr = BackupManager(temp_search_dir)
    with pytest.raises(ValueError, match="manifest version mismatch"):
        mgr.materialize_backup(
            backup_name="invalid_manifest_full",
            dest_dir=tmp_path / "materialized",
            verify_hashes=False,
        )


@pytest.mark.unit
def test_restore_from_backup_allows_mixed_version_metadata_fixture(temp_search_dir: Path):
    fixture = Path("tests/fixtures/storage/backup_contract_bundle")
    shutil.copytree(fixture, temp_search_dir, dirs_exist_ok=True)

    mgr = BackupManager(temp_search_dir)
    live_settings = temp_search_dir / "config" / "settings.toml"
    live_parquet = temp_search_dir / "data" / "conversations" / "conv.parquet"
    _write_bytes(live_settings, b"a = stale\n")
    _write_bytes(live_parquet, b"PAR1\nSTALE")

    mgr.restore_from_backup(
        temp_search_dir / "backups" / "mixed_version_metadata_full",
        create_pre_restore_backup=False,
        verify_hashes=False,
    )

    assert live_parquet.read_bytes().replace(b"\r\n", b"\n") == b"PAR1\n"


@pytest.mark.unit
def test_restore_from_backup_invalid_manifest_fixture_fails_closed(temp_search_dir: Path):
    fixture = Path("tests/fixtures/storage/backup_contract_bundle")
    shutil.copytree(fixture, temp_search_dir, dirs_exist_ok=True)

    mgr = BackupManager(temp_search_dir)
    with pytest.raises(ValueError, match="manifest version mismatch"):
        mgr.restore_from_backup(
            temp_search_dir / "backups" / "invalid_manifest_full",
            create_pre_restore_backup=False,
            verify_hashes=False,
        )


def _seed_duckdb_conversation(db_path: Path) -> None:
    """Create a minimal, schema-valid unified DuckDB with one conversation."""
    from searchat.storage.unified_storage import UnifiedStorage

    storage = UnifiedStorage(db_path)
    try:
        storage.connection.execute(
            "INSERT INTO conversations "
            "(conversation_id, project_id, file_path, title, created_at, updated_at, "
            "message_count, full_text, file_hash, indexed_at) "
            "VALUES ('c1', 'p1', '/tmp/c1.jsonl', 'Conv 1', now(), now(), 1, 'hello world', 'h1', now())"
        )
    finally:
        storage.close()


@pytest.mark.unit
def test_create_backup_default_excludes_derivable_index(temp_search_dir: Path) -> None:
    live = temp_search_dir
    mgr = BackupManager(live)

    _write_bytes(live / "data" / "conversations" / "conv.parquet", b"PAR1\n")
    _write_bytes(live / "data" / "indices" / "embeddings.faiss", b"FAISSSTUB")
    _seed_duckdb_conversation(live / "data" / "searchat.duckdb")

    from searchat.services.storage_contracts import BACKUP_SOURCE_SCHEMA_VERSION

    meta = mgr.create_backup(backup_name="snap")

    assert meta.excludes_derived is True
    assert meta.derived_schema_version == BACKUP_SOURCE_SCHEMA_VERSION

    manifest = mgr._load_manifest(meta.backup_path)
    assert manifest is not None
    assert "data/conversations/conv.parquet" in manifest.files
    assert "data/duckdb_source/conversations.parquet" in manifest.files
    assert "data/indices/embeddings.faiss" not in manifest.files
    assert not any(rel.startswith("data/searchat.duckdb") for rel in manifest.files)
    assert not (meta.backup_path / "data" / "indices").exists()
    assert not (meta.backup_path / "data" / "searchat.duckdb").exists()


@pytest.mark.unit
def test_create_backup_backs_up_new_state_directories_when_present(temp_search_dir: Path) -> None:
    live = temp_search_dir
    mgr = BackupManager(live)

    _write_bytes(live / "data" / "conversations" / "conv.parquet", b"PAR1\n")
    _write_bytes(live / "bookmarks.json", b"{}")
    _write_bytes(live / "saved_queries.json", b"{}")
    _write_bytes(live / "dashboards.json", b"{}")
    _write_bytes(live / "expertise" / "expertise.duckdb", b"stub")
    _write_bytes(live / "knowledge_graph" / "knowledge_graph.duckdb", b"stub")
    _write_bytes(live / "analytics" / "analytics.duckdb", b"stub")

    meta = mgr.create_backup(backup_name="snap")

    manifest = mgr._load_manifest(meta.backup_path)
    assert manifest is not None
    for rel in (
        "bookmarks.json",
        "saved_queries.json",
        "dashboards.json",
        "expertise/expertise.duckdb",
        "knowledge_graph/knowledge_graph.duckdb",
        "analytics/analytics.duckdb",
    ):
        assert rel in manifest.files, rel


@pytest.mark.unit
def test_create_backup_excludes_derived_false_keeps_legacy_full_copy(temp_search_dir: Path) -> None:
    live = temp_search_dir
    mgr = BackupManager(live)

    _write_bytes(live / "data" / "conversations" / "conv.parquet", b"PAR1\n")
    _write_bytes(live / "data" / "indices" / "embeddings.faiss", b"FAISSSTUB")
    _seed_duckdb_conversation(live / "data" / "searchat.duckdb")

    meta = mgr.create_backup(backup_name="snap", excludes_derived=False, compressed=False)

    assert meta.excludes_derived is False
    assert meta.derived_schema_version == 0

    manifest = mgr._load_manifest(meta.backup_path)
    assert manifest is not None
    assert "data/indices/embeddings.faiss" in manifest.files
    assert "data/searchat.duckdb" in manifest.files
    assert (meta.backup_path / "data" / "indices" / "embeddings.faiss").read_bytes() == b"FAISSSTUB"
    assert (meta.backup_path / "data" / "searchat.duckdb").exists()


@pytest.mark.unit
def test_source_of_truth_backup_is_materially_smaller_than_full_copy(temp_search_dir: Path) -> None:
    live = temp_search_dir
    mgr = BackupManager(live)

    _write_bytes(live / "data" / "conversations" / "conv.parquet", b"PAR1\n" * 100)
    # Inflate the derivable legacy index to >= 5x the source-of-truth payload.
    _write_bytes(live / "data" / "indices" / "embeddings.faiss", b"X" * (5 * 500 * 5))
    _write_bytes(live / "data" / "indices" / "embeddings.metadata.parquet", b"Y" * (5 * 500 * 5))

    source_of_truth = mgr.create_backup(backup_name="lean", compressed=False)
    full_copy = mgr.create_backup(backup_name="full", excludes_derived=False, compressed=False)

    assert source_of_truth.total_size_bytes < full_copy.total_size_bytes * 0.3



@pytest.mark.unit
def test_create_backup_default_compresses_plaintext_payload(temp_search_dir: Path) -> None:
    live = temp_search_dir
    mgr = BackupManager(live)

    _write_bytes(live / "data" / "conversations" / "conv.parquet", b"PAR1\n" * 1000)

    meta = mgr.create_backup(backup_name="snap")

    manifest = mgr._load_manifest(meta.backup_path)
    assert manifest is not None
    assert manifest.compressed is True

    file_meta = manifest.files["data/conversations/conv.parquet"]
    stored_rel = file_meta["stored_rel_path"]
    assert stored_rel == "data/conversations/conv.parquet.zst"
    assert (meta.backup_path / stored_rel).exists()
    assert not (meta.backup_path / "data" / "conversations" / "conv.parquet").exists()


@pytest.mark.unit
def test_create_backup_compressed_full_backup_is_not_snapshot_browsable(temp_search_dir: Path) -> None:
    live = temp_search_dir
    mgr = BackupManager(live)

    _write_bytes(live / "data" / "conversations" / "conv.parquet", b"PAR1\n")

    meta = mgr.create_backup(backup_name="snap")

    res = mgr.validate_backup_artifact(meta.backup_path.name, verify_hashes=False)
    assert res["valid"] is True
    assert res["snapshot_browsable"] is False


@pytest.mark.unit
def test_create_backup_compressed_false_stores_plaintext(temp_search_dir: Path) -> None:
    live = temp_search_dir
    mgr = BackupManager(live)

    _write_bytes(live / "data" / "conversations" / "conv.parquet", b"PAR1\n")

    meta = mgr.create_backup(backup_name="snap", compressed=False)

    manifest = mgr._load_manifest(meta.backup_path)
    assert manifest is not None
    assert manifest.compressed is False
    assert (meta.backup_path / "data" / "conversations" / "conv.parquet").read_bytes() == b"PAR1\n"


@pytest.mark.unit
def test_create_incremental_backup_compresses_changed_files(temp_search_dir: Path) -> None:
    live = temp_search_dir
    mgr = BackupManager(live)

    settings = live / "config" / "settings.toml"
    _write_bytes(settings, b"a = 1\n")
    base = mgr.create_backup(backup_name="base")

    _write_bytes(settings, b"a = 2\n" * 500)
    inc = mgr.create_incremental_backup(parent_name=base.backup_path.name, backup_name="inc")

    manifest = mgr._load_manifest(inc.backup_path)
    assert manifest is not None
    assert manifest.compressed is True
    assert manifest.files["config/settings.toml"]["stored_rel_path"] == "config/settings.toml.zst"


@pytest.mark.unit
def test_encrypted_backup_ignores_compressed_flag(temp_search_dir: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    import base64
    import os as _os

    monkeypatch.setenv("SEARCHAT_BACKUP_KEY_B64", base64.b64encode(_os.urandom(32)).decode("ascii"))

    live = temp_search_dir
    mgr = BackupManager(live)
    _write_bytes(live / "data" / "conversations" / "conv.parquet", b"PAR1\n")

    meta = mgr.create_backup(backup_name="enc", encrypted=True, compressed=True)

    manifest = mgr._load_manifest(meta.backup_path)
    assert manifest is not None
    assert manifest.encrypted is True
    assert manifest.compressed is False
    assert manifest.files["data/conversations/conv.parquet"]["stored_rel_path"] == "data/conversations/conv.parquet.enc"


def _write_backup_dir(
    backup_dir: Path,
    name: str,
    *,
    timestamp: str,
    pinned: bool = False,
    parent_name: str | None = None,
) -> None:
    """Build a minimal on-disk backup directory with controlled timestamp/pinned/parent."""
    from searchat.services.storage_contracts import BackupManifest, BackupMetadata

    path = backup_dir / name
    path.mkdir(parents=True, exist_ok=True)
    metadata = BackupMetadata(
        timestamp=timestamp,
        backup_path=path,
        source_path=backup_dir.parent,
        file_count=0,
        total_size_bytes=0,
        backup_type="manual",
        pinned=pinned,
    )
    (path / "backup_metadata.json").write_text(
        json.dumps(metadata.to_dict(), indent=2), encoding="utf-8"
    )
    manifest = BackupManifest(
        manifest_version=1,
        backup_mode="full" if parent_name is None else "incremental",
        encrypted=False,
        created_at=f"{timestamp}",
        parent_name=parent_name,
        files={},
        deleted_files=[],
    )
    (path / "backup_manifest.json").write_text(
        json.dumps(manifest.to_dict(), indent=2), encoding="utf-8"
    )


@pytest.mark.unit
def test_apply_retention_policy_keeps_last_n_and_prunes_rest(temp_search_dir: Path) -> None:
    mgr = BackupManager(temp_search_dir)
    for i in range(5):
        _write_backup_dir(mgr.backup_dir, f"snap{i}", timestamp=f"2026010{i + 1}_000000")

    result = mgr.apply_retention_policy(keep_last=2, keep_monthly=0)

    assert set(result.kept) == {"snap3", "snap4"}
    assert set(result.pruned) == {"snap0", "snap1", "snap2"}
    for name in result.pruned:
        assert not (mgr.backup_dir / name).exists()
    for name in result.kept:
        assert (mgr.backup_dir / name).exists()


@pytest.mark.unit
def test_apply_retention_policy_exempts_pinned_backups(temp_search_dir: Path) -> None:
    mgr = BackupManager(temp_search_dir)
    _write_backup_dir(mgr.backup_dir, "old_pinned", timestamp="20260101_000000", pinned=True)
    for i in range(3):
        _write_backup_dir(mgr.backup_dir, f"snap{i}", timestamp=f"2026020{i + 1}_000000")

    result = mgr.apply_retention_policy(keep_last=1, keep_monthly=0)

    assert "old_pinned" in result.kept
    assert (mgr.backup_dir / "old_pinned").exists()
    assert "snap2" in result.kept
    assert set(result.pruned) == {"snap0", "snap1"}


@pytest.mark.unit
def test_apply_retention_policy_keeps_one_per_month_beyond_keep_last(temp_search_dir: Path) -> None:
    mgr = BackupManager(temp_search_dir)
    _write_backup_dir(mgr.backup_dir, "jan_old", timestamp="20260105_000000")
    _write_backup_dir(mgr.backup_dir, "jan_new", timestamp="20260120_000000")
    _write_backup_dir(mgr.backup_dir, "feb", timestamp="20260210_000000")
    _write_backup_dir(mgr.backup_dir, "mar", timestamp="20260310_000000")

    result = mgr.apply_retention_policy(keep_last=1, keep_monthly=3)

    # keep_last=1 keeps "mar". Independently, keep_monthly=3 keeps the
    # newest backup in each of the 3 most recent distinct months: mar
    # (already kept), feb, and jan_new (the newest within January) --
    # the two rules' kept sets are unioned, not stacked.
    assert set(result.kept) == {"mar", "feb", "jan_new"}
    assert result.pruned == ("jan_old",)


@pytest.mark.unit
def test_apply_retention_policy_protects_chain_ancestors_of_kept_backups(temp_search_dir: Path) -> None:
    mgr = BackupManager(temp_search_dir)
    _write_backup_dir(mgr.backup_dir, "base", timestamp="20260101_000000")
    _write_backup_dir(mgr.backup_dir, "inc1", timestamp="20260102_000000", parent_name="base")
    _write_backup_dir(mgr.backup_dir, "inc2", timestamp="20260103_000000", parent_name="inc1")

    result = mgr.apply_retention_policy(keep_last=1, keep_monthly=0)

    # keep_last=1 keeps only inc2, but inc2's chain depends on inc1 and base.
    assert set(result.kept) == {"base", "inc1", "inc2"}
    assert result.pruned == ()


@pytest.mark.unit
def test_apply_retention_policy_dry_run_does_not_delete(temp_search_dir: Path) -> None:
    mgr = BackupManager(temp_search_dir)
    for i in range(3):
        _write_backup_dir(mgr.backup_dir, f"snap{i}", timestamp=f"2026010{i + 1}_000000")

    result = mgr.apply_retention_policy(keep_last=1, keep_monthly=0, dry_run=True)

    assert result.dry_run is True
    assert set(result.pruned) == {"snap0", "snap1"}
    for i in range(3):
        assert (mgr.backup_dir / f"snap{i}").exists()


@pytest.mark.unit
def test_set_pinned_toggles_flag_and_persists(temp_search_dir: Path) -> None:
    live = temp_search_dir
    mgr = BackupManager(live)
    _write_bytes(live / "data" / "conversations" / "conv.parquet", b"PAR1\n")
    meta = mgr.create_backup(backup_name="snap")
    name = meta.backup_path.name

    assert meta.pinned is False

    updated = mgr.set_pinned(name, True)
    assert updated.pinned is True

    reloaded = {b.backup_path.name: b for b in mgr.list_backups()}[name]
    assert reloaded.pinned is True

    unpinned = mgr.set_pinned(name, False)
    assert unpinned.pinned is False


@pytest.mark.unit
def test_set_pinned_missing_backup_raises(temp_search_dir: Path) -> None:
    mgr = BackupManager(temp_search_dir)
    with pytest.raises(FileNotFoundError):
        mgr.set_pinned("does_not_exist", True)
