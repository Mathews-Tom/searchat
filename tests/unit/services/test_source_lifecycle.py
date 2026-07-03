"""Unit tests for `searchat.services.source_lifecycle.verify_ingested`.

`verify_ingested` is the first, read-only stage of the M8 archive-then-prune
pipeline: it proves a source conversation file is fully and currently
indexed before any later stage is allowed to even consider deleting it.
These tests build real fixture DuckDB databases (via
`searchat.storage.schema.ensure_tables`) and real Claude-format `.jsonl`
fixture files, and exercise every branch of `verify_ingested` without any
filesystem mocking -- the function performs no mutation, so none is needed.

Only `verify_ingested` is covered here. `verify_roundtrip`, `archive_source`,
and `prune_source` are added to `source_lifecycle.py` by later milestones
and get their own test coverage in this same file at that point.
"""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timedelta
from pathlib import Path

import duckdb
import pytest

from searchat.core.connectors.claude import ClaudeConnector
from searchat.services.backup_compression import decompress_file
from searchat.services.source_lifecycle import VerificationResult, archive_source, verify_ingested
from searchat.storage.schema import ensure_tables

# ---------------------------------------------------------------------------
# Fixture helpers
# ---------------------------------------------------------------------------


def _write_claude_jsonl(path: Path, num_exchanges: int = 1) -> Path:
    """Write a real, minimal Claude-format JSONL fixture -- the exact shape
    `ClaudeConnector.parse()` expects: `type` in {"user", "assistant"},
    `message.content` as a plain string, and an ISO `timestamp`.

    Each exchange is one user line + one assistant line, so `num_exchanges`
    real messages a fresh parse will count is `2 * num_exchanges`.
    """
    base = datetime(2025, 1, 15, 10, 0, 0)
    entries: list[dict[str, object]] = []
    for i in range(num_exchanges):
        entries.append(
            {
                "type": "user",
                "message": {"content": f"Question {i}"},
                "timestamp": (base + timedelta(minutes=2 * i)).isoformat(),
            }
        )
        entries.append(
            {
                "type": "assistant",
                "message": {"content": f"Answer {i}"},
                "timestamp": (base + timedelta(minutes=2 * i, seconds=30)).isoformat(),
            }
        )
    path.write_text("\n".join(json.dumps(entry) for entry in entries) + "\n", encoding="utf-8")
    return path


def _new_db(tmp_path: Path, name: str = "state.duckdb") -> Path:
    """Create an empty but fully-migrated fixture DuckDB file."""
    db_path = tmp_path / name
    conn = duckdb.connect(str(db_path))
    try:
        ensure_tables(conn)
    finally:
        conn.close()
    return db_path


def _insert_source_file_state(
    db_path: Path,
    *,
    file_path: str,
    conversation_id: str | None,
    project_id: str = "proj",
    connector_name: str = "claude",
    status: str = "indexed",
    file_size: int = 0,
    file_hash: str | None,
    updated_at: datetime | None = None,
) -> None:
    conn = duckdb.connect(str(db_path))
    try:
        conn.execute(
            "INSERT INTO source_file_state "
            "(file_path, conversation_id, project_id, connector_name, status, "
            "file_size, file_hash, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            [
                file_path,
                conversation_id,
                project_id,
                connector_name,
                status,
                file_size,
                file_hash,
                updated_at or datetime.now(),
            ],
        )
    finally:
        conn.close()


def _insert_conversation(
    db_path: Path,
    *,
    conversation_id: str,
    file_path: str,
    message_count: int,
    project_id: str = "proj",
    title: str = "Test conversation",
    full_text: str = "some indexed text",
    file_hash: str = "unused-in-conversations-lookup",
) -> None:
    now = datetime.now()
    conn = duckdb.connect(str(db_path))
    try:
        conn.execute(
            "INSERT INTO conversations "
            "(conversation_id, project_id, file_path, title, created_at, updated_at, "
            "message_count, full_text, file_hash, indexed_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            [
                conversation_id,
                project_id,
                file_path,
                title,
                now,
                now,
                message_count,
                full_text,
                file_hash,
                now,
            ],
        )
    finally:
        conn.close()


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


# ---------------------------------------------------------------------------
# 1. Fully verified: hash and message count both match.
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_verify_ingested_returns_ok_when_hash_and_message_count_both_match(tmp_path: Path) -> None:
    source_file = _write_claude_jsonl(tmp_path / "conv-verified.jsonl", num_exchanges=1)
    connector = ClaudeConnector()
    real_hash = _sha256(source_file)
    real_message_count = connector.parse(source_file, embedding_id=0).message_count
    conversation_id = source_file.stem

    db_path = _new_db(tmp_path)
    _insert_source_file_state(
        db_path,
        file_path=str(source_file),
        conversation_id=conversation_id,
        file_hash=real_hash,
    )
    _insert_conversation(
        db_path,
        conversation_id=conversation_id,
        file_path=str(source_file),
        message_count=real_message_count,
    )

    result = verify_ingested(db_path, connector, source_file)

    assert isinstance(result, VerificationResult)
    assert result.ok is True
    assert result.reason is None


# ---------------------------------------------------------------------------
# 2. Missing source file on disk.
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_verify_ingested_fails_when_source_file_missing_from_disk(tmp_path: Path) -> None:
    missing_file = tmp_path / "never-written.jsonl"
    db_path = _new_db(tmp_path)

    result = verify_ingested(db_path, ClaudeConnector(), missing_file)

    assert result.ok is False
    assert result.reason
    assert "exist" in result.reason.lower()


# ---------------------------------------------------------------------------
# 3. No source_file_state row at all for that path.
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_verify_ingested_fails_when_no_source_file_state_row_exists(tmp_path: Path) -> None:
    source_file = _write_claude_jsonl(tmp_path / "conv-unknown.jsonl")
    db_path = _new_db(tmp_path)  # no source_file_state row inserted at all

    result = verify_ingested(db_path, ClaudeConnector(), source_file)

    assert result.ok is False
    assert result.reason
    assert "source_file_state" in result.reason.lower()


# ---------------------------------------------------------------------------
# 4. source_file_state.status is not 'indexed'.
# ---------------------------------------------------------------------------


@pytest.mark.unit
@pytest.mark.parametrize("bad_status", ["orphaned", "error"])
def test_verify_ingested_fails_when_status_is_not_indexed(tmp_path: Path, bad_status: str) -> None:
    source_file = _write_claude_jsonl(tmp_path / f"conv-{bad_status}.jsonl")
    real_hash = _sha256(source_file)
    conversation_id = source_file.stem

    db_path = _new_db(tmp_path)
    _insert_source_file_state(
        db_path,
        file_path=str(source_file),
        conversation_id=conversation_id,
        status=bad_status,
        file_hash=real_hash,
    )

    result = verify_ingested(db_path, ClaudeConnector(), source_file)

    assert result.ok is False
    assert result.reason
    assert "status" in result.reason.lower()
    assert bad_status in result.reason


# ---------------------------------------------------------------------------
# 5. Checksum mismatch: file changed on disk since it was indexed.
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_verify_ingested_fails_on_checksum_mismatch(tmp_path: Path) -> None:
    source_file = _write_claude_jsonl(tmp_path / "conv-modified.jsonl")
    conversation_id = source_file.stem
    wrong_hash = hashlib.sha256(b"this is not the real file content").hexdigest()
    assert wrong_hash != _sha256(source_file)

    db_path = _new_db(tmp_path)
    _insert_source_file_state(
        db_path,
        file_path=str(source_file),
        conversation_id=conversation_id,
        file_hash=wrong_hash,
    )

    result = verify_ingested(db_path, ClaudeConnector(), source_file)

    assert result.ok is False
    assert result.reason
    assert "hash" in result.reason.lower() or "checksum" in result.reason.lower()


# ---------------------------------------------------------------------------
# 6. Message-count mismatch: checksum is correct but the indexed
#    conversations row disagrees with a fresh re-parse.
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_verify_ingested_fails_on_message_count_mismatch(tmp_path: Path) -> None:
    source_file = _write_claude_jsonl(tmp_path / "conv-partial-index.jsonl", num_exchanges=1)
    connector = ClaudeConnector()
    real_hash = _sha256(source_file)
    real_message_count = connector.parse(source_file, embedding_id=0).message_count
    conversation_id = source_file.stem
    wrong_message_count = real_message_count + 3
    assert wrong_message_count != real_message_count

    db_path = _new_db(tmp_path)
    _insert_source_file_state(
        db_path,
        file_path=str(source_file),
        conversation_id=conversation_id,
        file_hash=real_hash,
    )
    _insert_conversation(
        db_path,
        conversation_id=conversation_id,
        file_path=str(source_file),
        message_count=wrong_message_count,
    )

    result = verify_ingested(db_path, connector, source_file)

    assert result.ok is False
    assert result.reason
    assert "message count" in result.reason.lower()


# ---------------------------------------------------------------------------
# 7. source_file_state row has a null/empty conversation_id.
# ---------------------------------------------------------------------------


@pytest.mark.unit
@pytest.mark.parametrize("empty_conversation_id", [None, ""])
def test_verify_ingested_fails_when_conversation_id_is_null_or_empty(
    tmp_path: Path, empty_conversation_id: str | None
) -> None:
    source_file = _write_claude_jsonl(tmp_path / "conv-no-id.jsonl")
    real_hash = _sha256(source_file)

    db_path = _new_db(tmp_path)
    _insert_source_file_state(
        db_path,
        file_path=str(source_file),
        conversation_id=empty_conversation_id,
        file_hash=real_hash,
    )

    result = verify_ingested(db_path, ClaudeConnector(), source_file)

    assert result.ok is False
    assert result.reason
    assert "conversation_id" in result.reason.lower()


# ---------------------------------------------------------------------------
# 8. conversation_id present in source_file_state but absent from
#    conversations.
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_verify_ingested_fails_when_conversation_id_has_no_matching_conversations_row(
    tmp_path: Path,
) -> None:
    source_file = _write_claude_jsonl(tmp_path / "conv-orphaned-id.jsonl")
    real_hash = _sha256(source_file)
    conversation_id = source_file.stem

    db_path = _new_db(tmp_path)
    _insert_source_file_state(
        db_path,
        file_path=str(source_file),
        conversation_id=conversation_id,
        file_hash=real_hash,
    )
    # deliberately no matching row inserted into `conversations`

    result = verify_ingested(db_path, ClaudeConnector(), source_file)

    assert result.ok is False
    assert result.reason
    assert conversation_id in result.reason
    assert "conversations" in result.reason.lower()

# ---------------------------------------------------------------------------
# archive_source: zstd-compress-then-verify-then-delete (M8).
#
# These tests exercise the real zstandard compress/decompress round trip
# against real files on disk -- no mocking -- because a bug here can
# destroy user data (see module docstring). Every scenario asserts the
# original file's fate: deleted only on a fully verified success, left
# byte-for-byte untouched on any failure.
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_archive_source_compresses_deletes_original_and_roundtrips(tmp_path: Path) -> None:
    source_file = _write_claude_jsonl(tmp_path / "conv-archive.jsonl", num_exchanges=200)
    original_bytes = source_file.read_bytes()
    assert len(original_bytes) > 2000  # "a few KB", not a token fixture

    result = archive_source(source_file)

    assert result == source_file.with_name(source_file.name + ".zst")
    assert result.exists()
    assert not source_file.exists()

    decompressed = tmp_path / "roundtrip-decompressed.jsonl"
    decompress_file(result, decompressed)
    assert decompressed.read_bytes() == original_bytes
    assert _sha256(decompressed) == hashlib.sha256(original_bytes).hexdigest()


@pytest.mark.unit
def test_archive_source_raises_file_not_found_for_missing_source(tmp_path: Path) -> None:
    missing_file = tmp_path / "never-written.jsonl"

    with pytest.raises(FileNotFoundError):
        archive_source(missing_file)

    assert not missing_file.with_name(missing_file.name + ".zst").exists()


@pytest.mark.unit
def test_archive_source_raises_file_exists_and_leaves_both_files_untouched(tmp_path: Path) -> None:
    source_file = _write_claude_jsonl(tmp_path / "conv-target-exists.jsonl")
    archived_path = source_file.with_name(source_file.name + ".zst")
    archived_path.write_bytes(b"not a real zst archive -- arbitrary pre-existing content")

    source_bytes_before = source_file.read_bytes()
    archived_bytes_before = archived_path.read_bytes()

    with pytest.raises(FileExistsError):
        archive_source(source_file)

    assert source_file.read_bytes() == source_bytes_before
    assert archived_path.read_bytes() == archived_bytes_before


@pytest.mark.unit
def test_archive_source_with_custom_compression_level_still_roundtrips(tmp_path: Path) -> None:
    source_file = _write_claude_jsonl(tmp_path / "conv-archive-level9.jsonl", num_exchanges=200)
    original_bytes = source_file.read_bytes()

    result = archive_source(source_file, compression_level=9)

    assert result == source_file.with_name(source_file.name + ".zst")
    assert result.exists()
    assert not source_file.exists()

    decompressed = tmp_path / "roundtrip-decompressed-level9.jsonl"
    decompress_file(result, decompressed)
    assert decompressed.read_bytes() == original_bytes


@pytest.mark.unit
def test_archive_source_roundtrips_empty_file(tmp_path: Path) -> None:
    empty_file = tmp_path / "empty.jsonl"
    empty_file.write_bytes(b"")

    result = archive_source(empty_file)

    assert result == empty_file.with_name(empty_file.name + ".zst")
    assert result.exists()
    assert not empty_file.exists()

    decompressed = tmp_path / "roundtrip-decompressed-empty.jsonl"
    decompress_file(result, decompressed)
    assert decompressed.exists()
    assert decompressed.read_bytes() == b""
