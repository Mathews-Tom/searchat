from __future__ import annotations

import base64
import os
from pathlib import Path

import pytest

from searchat.services.backup import BackupManager


def _write_bytes(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)


def _set_env_key(monkeypatch: pytest.MonkeyPatch, key: bytes) -> None:
    monkeypatch.setenv("SEARCHAT_BACKUP_KEY_B64", base64.b64encode(key).decode("ascii"))


@pytest.mark.unit
def test_encrypted_full_backup_validate_and_restore(monkeypatch: pytest.MonkeyPatch, temp_search_dir: Path):
    _set_env_key(monkeypatch, os.urandom(32))
    live = temp_search_dir
    mgr = BackupManager(live)

    parquet = live / "data" / "conversations" / "conv.parquet"
    settings = live / "config" / "settings.toml"
    _write_bytes(parquet, b"PAR1\n")
    _write_bytes(settings, b"a = 1\n")

    meta = mgr.create_backup(backup_name="enc", encrypted=True)
    name = meta.backup_path.name

    res = mgr.validate_backup_artifact(name, verify_hashes=True)
    assert res["valid"] is True
    assert res["encrypted"] is True
    assert res["snapshot_browsable"] is False

    # Break the live dataset, then restore from encrypted backup.
    _write_bytes(settings, b"a = 999\n")
    parquet.unlink()
    mgr.restore_from_backup(meta.backup_path, create_pre_restore_backup=False)

    assert settings.read_bytes() == b"a = 1\n"
    assert parquet.read_bytes() == b"PAR1\n"


@pytest.mark.unit
def test_encrypted_incremental_backup_restore(monkeypatch: pytest.MonkeyPatch, temp_search_dir: Path):
    _set_env_key(monkeypatch, os.urandom(32))
    live = temp_search_dir
    mgr = BackupManager(live)

    parquet = live / "data" / "conversations" / "conv.parquet"
    settings = live / "config" / "settings.toml"
    removed = live / "data" / "indices" / "removed.bin"
    added = live / "data" / "indices" / "added.bin"

    _write_bytes(parquet, b"PAR1\n")
    _write_bytes(settings, b"a = 1\n")
    _write_bytes(removed, b"old\n")

    base = mgr.create_backup(backup_name="base", encrypted=True)
    base_name = base.backup_path.name

    # Create delta.
    _write_bytes(settings, b"a = 2\n")
    removed.unlink()
    _write_bytes(added, b"new\n")
    inc = mgr.create_incremental_backup(parent_name=base_name, backup_name="inc", encrypted=True)

    # Break live and restore from incremental.
    _write_bytes(settings, b"a = 999\n")
    _write_bytes(removed, b"wrong\n")
    added.unlink()
    mgr.restore_from_backup(inc.backup_path, create_pre_restore_backup=False)

    assert settings.read_bytes() == b"a = 2\n"
    assert not removed.exists()
    assert (live / "data" / "indices" / "added.bin").read_bytes() == b"new\n"
    assert parquet.read_bytes() == b"PAR1\n"


@pytest.mark.unit
def test_encrypted_restore_fails_with_wrong_key(monkeypatch: pytest.MonkeyPatch, temp_search_dir: Path):
    key1 = os.urandom(32)
    _set_env_key(monkeypatch, key1)

    live = temp_search_dir
    mgr = BackupManager(live)

    parquet = live / "data" / "conversations" / "conv.parquet"
    _write_bytes(parquet, b"PAR1\n")

    meta = mgr.create_backup(backup_name="enc", encrypted=True)

    # Swap key and attempt restore.
    _set_env_key(monkeypatch, os.urandom(32))
    with pytest.raises(ValueError, match="authentication failed"):
        mgr.restore_from_backup(meta.backup_path, create_pre_restore_backup=False)
