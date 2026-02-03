from __future__ import annotations

import base64
import os
from pathlib import Path


ENV_BACKUP_KEY_B64 = "SEARCHAT_BACKUP_KEY_B64"
ENV_KEYRING_SERVICE = "SEARCHAT_BACKUP_KEYRING_SERVICE"

KEYRING_DEFAULT_SERVICE = "searchat"
KEYRING_USERNAME = "backup_key_v1"

MAGIC = b"SAT1"
NONCE_SIZE = 12
TAG_SIZE = 16


def _load_cryptography():
    try:
        from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
        from cryptography.exceptions import InvalidTag

        return Cipher, algorithms, modes, InvalidTag
    except Exception as e:  # pragma: no cover
        raise RuntimeError(
            "Backup encryption requires 'cryptography'. Install with: uv pip install 'searchat[secure]'"
        ) from e


def _load_keyring():
    try:
        import keyring

        return keyring
    except Exception as e:  # pragma: no cover
        raise RuntimeError(
            "Keyring-based key storage requires 'keyring'. Install with: uv pip install 'searchat[secure]'"
        ) from e


def get_backup_key() -> bytes:
    """Return the backup encryption key.

    Order:
    - If SEARCHAT_BACKUP_KEY_B64 is set: use it.
    - Else: load/create a key in the OS keychain via keyring.

    Raises:
        RuntimeError: If no key source is available.
        ValueError: If the provided key is invalid.
    """
    raw = os.environ.get(ENV_BACKUP_KEY_B64)
    if raw:
        try:
            key = base64.b64decode(raw)
        except Exception as e:
            raise ValueError("Invalid base64 in SEARCHAT_BACKUP_KEY_B64") from e
        if len(key) != 32:
            raise ValueError("SEARCHAT_BACKUP_KEY_B64 must decode to 32 bytes")
        return key

    keyring = _load_keyring()
    service = os.environ.get(ENV_KEYRING_SERVICE, KEYRING_DEFAULT_SERVICE)
    existing = keyring.get_password(service, KEYRING_USERNAME)
    if existing:
        key = base64.b64decode(existing)
        if len(key) != 32:
            raise ValueError("Stored keyring key has invalid length")
        return key

    key = os.urandom(32)
    keyring.set_password(service, KEYRING_USERNAME, base64.b64encode(key).decode("ascii"))
    return key


def encrypt_file(src: Path, dst: Path, *, key: bytes) -> tuple[str, str, int]:
    """Encrypt src -> dst using AES-GCM.

    Returns:
        (content_sha256, stored_sha256, stored_size_bytes)
    """
    Cipher, algorithms, modes, _InvalidTag = _load_cryptography()

    nonce = os.urandom(NONCE_SIZE)
    cipher = Cipher(algorithms.AES(key), modes.GCM(nonce))
    encryptor = cipher.encryptor()

    import hashlib

    content_h = hashlib.sha256()
    stored_h = hashlib.sha256()

    dst.parent.mkdir(parents=True, exist_ok=True)
    with open(dst, "wb") as out, open(src, "rb") as inp:
        header = MAGIC + nonce
        out.write(header)
        stored_h.update(header)
        for chunk in iter(lambda: inp.read(1024 * 1024), b""):
            content_h.update(chunk)
            ct = encryptor.update(chunk)
            if ct:
                out.write(ct)
                stored_h.update(ct)

        encryptor.finalize()
        tag = encryptor.tag
        if len(tag) != TAG_SIZE:
            raise RuntimeError("Unexpected GCM tag length")
        out.write(tag)
        stored_h.update(tag)

    return content_h.hexdigest(), stored_h.hexdigest(), dst.stat().st_size


def decrypt_file(src: Path, dst: Path, *, key: bytes) -> None:
    """Decrypt src -> dst using AES-GCM."""
    Cipher, algorithms, modes, InvalidTag = _load_cryptography()

    with open(src, "rb") as inp:
        header = inp.read(len(MAGIC) + NONCE_SIZE)
        if len(header) != len(MAGIC) + NONCE_SIZE or not header.startswith(MAGIC):
            raise ValueError("Invalid encrypted backup file header")
        nonce = header[len(MAGIC) :]

        inp.seek(0, os.SEEK_END)
        size = inp.tell()
        if size < len(MAGIC) + NONCE_SIZE + TAG_SIZE:
            raise ValueError("Invalid encrypted backup file size")
        inp.seek(size - TAG_SIZE)
        tag = inp.read(TAG_SIZE)

        cipher = Cipher(algorithms.AES(key), modes.GCM(nonce, tag))
        decryptor = cipher.decryptor()

        inp.seek(len(MAGIC) + NONCE_SIZE)
        remaining = size - (len(MAGIC) + NONCE_SIZE + TAG_SIZE)

        dst.parent.mkdir(parents=True, exist_ok=True)
        with open(dst, "wb") as out:
            while remaining > 0:
                chunk = inp.read(min(1024 * 1024, remaining))
                if not chunk:
                    raise ValueError("Unexpected EOF while decrypting")
                remaining -= len(chunk)
                pt = decryptor.update(chunk)
                if pt:
                    out.write(pt)
            try:
                decryptor.finalize()
            except InvalidTag as e:
                raise ValueError("Encrypted backup authentication failed") from e
