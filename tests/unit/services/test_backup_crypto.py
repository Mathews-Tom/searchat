"""Tests for searchat.services.backup_crypto low-level functions."""
from __future__ import annotations

import base64
import os
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from searchat.services.backup_crypto import (
    MAGIC,
    NONCE_SIZE,
    decrypt_file,
    encrypt_file,
    get_backup_key,
)


# ── get_backup_key() ──────────────────────────────────────────────

def test_get_backup_key_from_env(monkeypatch: pytest.MonkeyPatch):
    key = os.urandom(32)
    monkeypatch.setenv("SEARCHAT_BACKUP_KEY_B64", base64.b64encode(key).decode("ascii"))
    assert get_backup_key() == key


def test_get_backup_key_invalid_base64(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("SEARCHAT_BACKUP_KEY_B64", "not-valid-base64!!!")
    with pytest.raises(ValueError, match="Invalid base64"):
        get_backup_key()


def test_get_backup_key_wrong_length(monkeypatch: pytest.MonkeyPatch):
    short_key = os.urandom(16)
    monkeypatch.setenv("SEARCHAT_BACKUP_KEY_B64", base64.b64encode(short_key).decode("ascii"))
    with pytest.raises(ValueError, match="32 bytes"):
        get_backup_key()


def test_get_backup_key_keyring_existing(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.delenv("SEARCHAT_BACKUP_KEY_B64", raising=False)
    key = os.urandom(32)
    encoded = base64.b64encode(key).decode("ascii")
    mock_keyring = Mock()
    mock_keyring.get_password.return_value = encoded
    with patch("searchat.services.backup_crypto._load_keyring", return_value=mock_keyring):
        assert get_backup_key() == key


def test_get_backup_key_keyring_generates_new(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.delenv("SEARCHAT_BACKUP_KEY_B64", raising=False)
    mock_keyring = Mock()
    mock_keyring.get_password.return_value = None
    with patch("searchat.services.backup_crypto._load_keyring", return_value=mock_keyring):
        result = get_backup_key()
    assert len(result) == 32
    mock_keyring.set_password.assert_called_once()


# ── encrypt_file() / decrypt_file() round-trip ───────────────────

def test_encrypt_decrypt_round_trip(tmp_path: Path):
    key = os.urandom(32)
    src = tmp_path / "original.bin"
    encrypted = tmp_path / "encrypted.bin"
    decrypted = tmp_path / "decrypted.bin"

    content = b"searchat test data " * 100
    src.write_bytes(content)

    content_hash, stored_hash, stored_size = encrypt_file(src, encrypted, key=key)
    assert encrypted.exists()
    assert stored_size == encrypted.stat().st_size
    assert len(content_hash) == 64
    assert len(stored_hash) == 64

    decrypt_file(encrypted, decrypted, key=key)
    assert decrypted.read_bytes() == content


def test_decrypt_invalid_header(tmp_path: Path):
    key = os.urandom(32)
    bad_file = tmp_path / "bad.bin"
    bad_file.write_bytes(b"XXXX" + os.urandom(100))

    with pytest.raises(ValueError, match="Invalid encrypted backup file header"):
        decrypt_file(bad_file, tmp_path / "out.bin", key=key)


def test_decrypt_truncated_file(tmp_path: Path):
    key = os.urandom(32)
    short_file = tmp_path / "short.bin"
    short_file.write_bytes(MAGIC + os.urandom(NONCE_SIZE))

    with pytest.raises(ValueError, match="Invalid encrypted backup file size"):
        decrypt_file(short_file, tmp_path / "out.bin", key=key)
