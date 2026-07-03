from __future__ import annotations

from pathlib import Path

import pytest

from searchat.services.backup_compression import compress_file, decompress_file


@pytest.mark.unit
def test_compress_file_roundtrips_content(tmp_path: Path) -> None:
    src = tmp_path / "source.txt"
    src.write_bytes(b"hello world\n" * 1000)

    dst = tmp_path / "compressed.zst"
    content_sha, stored_sha, stored_size = compress_file(src, dst, level=3)

    assert dst.exists()
    assert stored_size == dst.stat().st_size
    assert stored_size < src.stat().st_size

    restored = tmp_path / "restored.txt"
    decompress_file(dst, restored)

    assert restored.read_bytes() == src.read_bytes()

    import hashlib

    assert content_sha == hashlib.sha256(src.read_bytes()).hexdigest()
    assert stored_sha == hashlib.sha256(dst.read_bytes()).hexdigest()
    assert content_sha != stored_sha


@pytest.mark.unit
def test_compress_file_content_hash_independent_of_compression_level(tmp_path: Path) -> None:
    src = tmp_path / "source.bin"
    src.write_bytes(b"\x00\x01\x02" * 5000)

    dst_low = tmp_path / "low.zst"
    dst_high = tmp_path / "high.zst"
    content_sha_low, _, _ = compress_file(src, dst_low, level=1)
    content_sha_high, _, _ = compress_file(src, dst_high, level=19)

    assert content_sha_low == content_sha_high


@pytest.mark.unit
def test_decompress_file_creates_parent_directories(tmp_path: Path) -> None:
    src = tmp_path / "source.txt"
    src.write_bytes(b"payload")
    compressed = tmp_path / "compressed.zst"
    compress_file(src, compressed, level=3)

    dst = tmp_path / "nested" / "deep" / "restored.txt"
    decompress_file(compressed, dst)

    assert dst.read_bytes() == b"payload"
