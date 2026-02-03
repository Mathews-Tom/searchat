from __future__ import annotations

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
    removed = live / "data" / "indices" / "removed.bin"
    added = live / "data" / "indices" / "added.bin"

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
    assert not (out / "data" / "indices" / "removed.bin").exists()
    assert (out / "data" / "indices" / "added.bin").read_bytes() == b"new\n"
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
    removed = live / "data" / "indices" / "removed.bin"
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
    meta = mgr.create_backup(backup_name="base")
    name = meta.backup_path.name

    # Tamper with a copied file in the backup.
    tamper = meta.backup_path / "data" / "conversations" / "conv.parquet"
    _write_bytes(tamper, b"PAR1\nTAMPER")

    res = mgr.validate_backup_artifact(name, verify_hashes=True)
    assert res["valid"] is False
    assert any("Hash mismatch" in e for e in res.get("errors", []))
