"""zstd compression for plaintext backup payloads (M4).

Mirrors `services/backup_crypto.py`'s file-to-file API shape
(`content_sha256`/`stored_sha256`/`stored_size_bytes`) so
`services/backup.py` can treat compression as a third storage mode
alongside plaintext and encrypted, without changing how the manifest
tracks file hashes.

Compression and encryption are independent, mutually exclusive storage
modes for a given backup: M4 only compresses the plaintext path,
matching its own out-of-scope note ("Encryption changes... untouched").
"""
from __future__ import annotations

import hashlib
from pathlib import Path

import zstandard as zstd

_CHUNK_SIZE = 1024 * 1024


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(_CHUNK_SIZE), b""):
            h.update(chunk)
    return h.hexdigest()


def compress_file(src: Path, dst: Path, *, level: int) -> tuple[str, str, int]:
    """Compress src -> dst with zstd.

    Returns:
        (content_sha256, stored_sha256, stored_size_bytes) -- the first
        two mirror `backup_crypto.encrypt_file`'s contract: content_sha256
        hashes the original uncompressed bytes, stored_sha256 hashes the
        compressed bytes actually written to disk.
    """
    dst.parent.mkdir(parents=True, exist_ok=True)
    content_h = hashlib.sha256()
    compressor = zstd.ZstdCompressor(level=level)
    with open(src, "rb") as inp, open(dst, "wb") as out:
        with compressor.stream_writer(out) as writer:
            for chunk in iter(lambda: inp.read(_CHUNK_SIZE), b""):
                content_h.update(chunk)
                writer.write(chunk)
    return content_h.hexdigest(), _sha256_file(dst), dst.stat().st_size


def decompress_file(src: Path, dst: Path) -> None:
    """Decompress src -> dst with zstd."""
    dst.parent.mkdir(parents=True, exist_ok=True)
    decompressor = zstd.ZstdDecompressor()
    with open(src, "rb") as inp, open(dst, "wb") as out:
        with decompressor.stream_reader(inp) as reader:
            for chunk in iter(lambda: reader.read(_CHUNK_SIZE), b""):
                out.write(chunk)
