"""Source conversation-file lifecycle: verified archive-then-prune (M8).

CRITICAL: this module is the only place in Searchat allowed to delete a
harness's source conversation file. The project has already lost source
JSONLs to an over-eager reindex once; every capability added here is
gated so that a bug can only make the tool do LESS, never MORE, than a
human explicitly asked for:

- ``prune_source``/``archive_source`` never run implicitly -- callers
  (the ``sources`` CLI, see ``cli/sources_cmd.py``) must explicitly opt
  out of ``dry_run`` per invocation.
- Both ``verify_ingested`` and ``verify_roundtrip`` must pass before any
  mutation is even considered -- enforced by ``evaluate_candidate``
  returning ``eligible=False`` otherwise, not by caller discipline.
- Every successful archive/prune writes exactly one append-only
  tombstone entry recording enough provenance (checksum, connector,
  conversation id, Parquet message count) to know what was removed and
  why the pipeline believed it was safe to do so.

Two-stage verification pipeline, per source file:

1. ``verify_ingested`` -- structural proof the file is fully, currently
   indexed: its on-disk checksum matches what Searchat indexed, and a
   fresh re-parse's message count matches the ``conversations`` row
   already in Parquet. Read-only.
2. ``verify_roundtrip`` -- structural proof the file's content can be
   regenerated from Parquet alone: the connector's ``export_original``
   is re-parsed and diffed field-by-field against the stored record.
   Read-only (writes only to a throwaway temp directory, never to the
   source file or its siblings).

Only once both pass -- and the connector is age-gated and explicitly
opted into ``lifecycle.enabled_agents`` -- may ``archive_source`` (zstd
in place) or ``prune_source`` (delete) run.
"""
from __future__ import annotations

import hashlib
import tempfile
from dataclasses import dataclass
from pathlib import Path

import duckdb

from searchat.core.connectors.base import AgentProviderBase
from searchat.core.logging_config import get_logger
from searchat.models import ConversationRecord
from searchat.services.backup_compression import compress_file, decompress_file

logger = get_logger(__name__)


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


@dataclass(frozen=True)
class VerificationResult:
    """Verdict from one verification stage (`verify_ingested` or
    `verify_roundtrip`). `ok=False` always carries a human-readable `reason`
    so a refused archive/prune is explainable, not a silent no-op."""

    ok: bool
    reason: str | None = None

    def to_dict(self) -> dict[str, object]:
        return {"ok": self.ok, "reason": self.reason}


_SOURCE_FILE_STATE_COLUMNS = (
    "file_path",
    "conversation_id",
    "project_id",
    "connector_name",
    "status",
    "file_size",
    "file_hash",
    "updated_at",
)


def _read_source_file_state(
    db_path: Path,
    file_path: Path,
    *,
    connection: duckdb.DuckDBPyConnection | None = None,
) -> dict[str, object] | None:
    """Fetch the `source_file_state` row for `file_path`, or `None`.

    Mirrors `services/disk_accounting.py`'s connection-reuse pattern: a
    live server connection is reused via a fresh cursor (DuckDB refuses a
    second same-process connection once the first has non-default config);
    the CLI path opens its own short-lived read-only connection.
    """
    query = (
        "SELECT " + ", ".join(_SOURCE_FILE_STATE_COLUMNS) + " "
        "FROM source_file_state WHERE file_path = ? LIMIT 1"
    )
    params = [str(file_path)]

    if connection is not None:
        cur = connection.cursor()
        try:
            row = cur.execute(query, params).fetchone()
        except duckdb.Error:
            return None
        finally:
            cur.close()
    else:
        if not db_path.exists():
            return None
        con = duckdb.connect(str(db_path), read_only=True)
        try:
            row = con.execute(query, params).fetchone()
        except duckdb.Error:
            return None
        finally:
            con.close()

    if row is None:
        return None
    return dict(zip(_SOURCE_FILE_STATE_COLUMNS, row))


def _read_conversation_meta(
    db_path: Path,
    conversation_id: str,
    *,
    connection: duckdb.DuckDBPyConnection | None = None,
) -> dict[str, object] | None:
    """Fetch `{conversation_id, message_count}` from `conversations`, or `None`."""
    query = "SELECT conversation_id, message_count FROM conversations WHERE conversation_id = ? LIMIT 1"
    params = [conversation_id]

    if connection is not None:
        cur = connection.cursor()
        try:
            row = cur.execute(query, params).fetchone()
        except duckdb.Error:
            return None
        finally:
            cur.close()
    else:
        if not db_path.exists():
            return None
        con = duckdb.connect(str(db_path), read_only=True)
        try:
            row = con.execute(query, params).fetchone()
        except duckdb.Error:
            return None
        finally:
            con.close()

    if row is None:
        return None
    return {"conversation_id": row[0], "message_count": row[1]}


def verify_ingested(
    db_path: Path,
    connector: AgentProviderBase,
    file_path: Path,
    *,
    connection: duckdb.DuckDBPyConnection | None = None,
) -> VerificationResult:
    """Structural proof that `file_path` is fully, currently ingested.

    Two independent checks, both required to pass:

    1. Checksum parity -- the file's current on-disk SHA-256 must equal
       the hash `source_file_state` recorded at ingestion time. A
       mismatch means the file changed (or was never indexed), so
       whatever Searchat has in Parquet may not reflect its full content.
    2. Message-count parity -- re-parsing the file with its owning
       connector must yield the same `message_count` already stored on
       the `conversations` row. A mismatch means the index only captured
       a partial ingest (e.g. an interrupted indexing run), which a
       checksum match alone would not catch if the file was rewritten
       identically after a partial index.

    Read-only: only ever opens `file_path` and `db_path` for reading.
    """
    if not file_path.is_file():
        return VerificationResult(False, "source file does not exist on disk")

    row = _read_source_file_state(db_path, file_path, connection=connection)
    if row is None:
        return VerificationResult(False, "no source_file_state row for this path")
    if row["status"] != "indexed":
        return VerificationResult(False, f"source_file_state status is {row['status']!r}, not 'indexed'")

    conversation_id = row["conversation_id"]
    if not conversation_id or not isinstance(conversation_id, str):
        return VerificationResult(False, "source_file_state row has no conversation_id")

    indexed_hash = row["file_hash"]
    if not indexed_hash:
        return VerificationResult(False, "source_file_state row has no recorded file_hash")

    current_hash = _sha256_file(file_path)
    if current_hash != indexed_hash:
        return VerificationResult(False, "on-disk file hash differs from the indexed hash")

    meta = _read_conversation_meta(db_path, conversation_id, connection=connection)
    if meta is None:
        return VerificationResult(False, f"conversation_id {conversation_id!r} not found in conversations table")

    try:
        reparsed = connector.parse(file_path, embedding_id=0)
    except Exception as exc:
        return VerificationResult(False, f"re-parse for message-count check failed: {exc}")

    indexed_count = meta["message_count"]
    if reparsed.message_count != indexed_count:
        return VerificationResult(
            False,
            "message count mismatch: on-disk re-parse="
            f"{reparsed.message_count}, indexed Parquet={indexed_count}",
        )

    return VerificationResult(True)


@dataclass(frozen=True)
class RoundtripResult:
    """Verdict from `verify_roundtrip`: the reversibility proof gating
    `archive_source`/`prune_source`. `ok=False` always carries a `reason`
    and, when the two records were compared field-by-field, the exact
    `mismatches` -- never a silent refusal."""

    ok: bool
    reason: str | None = None
    mismatches: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, object]:
        return {"ok": self.ok, "reason": self.reason, "mismatches": list(self.mismatches)}


# Fields compared between the stored record and the export-then-reparse
# result. Deliberately excludes `file_path` (the reparse always happens at
# a throwaway mirrored path, never the original), `file_hash` (the
# re-serialized bytes are a different, connector-native encoding of the
# same content, not a byte-identical copy), `embedding_id` (passed through
# unchanged, not derived), and `indexed_at` (a wall-clock stamp, not
# content).
_COMPARABLE_FIELDS: tuple[str, ...] = (
    "conversation_id",
    "project_id",
    "title",
    "created_at",
    "updated_at",
    "message_count",
    "messages",
    "full_text",
    "files_mentioned",
    "git_branch",
)


def _comparable(record: ConversationRecord) -> dict[str, object]:
    return {name: getattr(record, name) for name in _COMPARABLE_FIELDS}


def verify_roundtrip(connector: AgentProviderBase, record: ConversationRecord) -> RoundtripResult:
    """Reversibility proof: `connector.export_original(record)` must produce
    bytes that, once written back to a path preserving `record.file_path`'s
    directory structure and re-parsed, reproduce a `ConversationRecord`
    equal to `record` in every field forensic recovery could rely on.

    The export is written under a throwaway `tempfile.TemporaryDirectory`,
    mirroring `record.file_path`'s structure relative to its filesystem
    root -- never the original path itself, and never any of its sibling
    files -- so this function cannot write to, or otherwise disturb, the
    real source file it is verifying. Some connectors derive part of a
    conversation's identity from the parent (or grandparent) directory
    name rather than file content (e.g. Claude's `project_id`, Gemini's
    project hash); mirroring the full relative path, not just the
    filename, preserves that identity without this function needing any
    connector-specific knowledge.
    """
    try:
        exported = connector.export_original(record)
    except Exception as exc:
        return RoundtripResult(False, reason=f"export_original raised: {exc}")

    original_path = Path(record.file_path)
    try:
        with tempfile.TemporaryDirectory(prefix="searchat-roundtrip-") as tmp_dir:
            anchor = original_path.anchor or "/"
            relative = (
                original_path.relative_to(anchor) if original_path.is_absolute() else original_path
            )
            target = Path(tmp_dir) / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(exported)
            try:
                reparsed = connector.parse(target, record.embedding_id)
            except Exception as exc:
                return RoundtripResult(False, reason=f"re-parse of exported bytes failed: {exc}")
    except OSError as exc:
        return RoundtripResult(False, reason=f"failed to materialize exported bytes: {exc}")

    stored_view = _comparable(record)
    reparsed_view = _comparable(reparsed)
    mismatches = tuple(
        sorted(name for name in _COMPARABLE_FIELDS if stored_view[name] != reparsed_view[name])
    )
    if mismatches:
        return RoundtripResult(
            False, reason="re-parsed record differs from the stored record", mismatches=mismatches
        )
    return RoundtripResult(True)


def archive_source(file_path: Path, *, compression_level: int = 3) -> Path:
    """Zstd-compress `file_path` in place, replacing it with `<name>.zst`.

    Verifies the compressed file decompresses back to byte-identical
    content -- via a real decompress-to-a-temp-file round trip, not just
    an in-memory hash -- BEFORE removing the original, mirroring
    `services/compaction.py`'s verify-before-destructive-step pattern.
    The original is left completely untouched on any failure: a missing
    source, an existing `.zst` target, or a failed verification all raise
    before `file_path.unlink()` is ever reached.

    Callers (`services.source_lifecycle`'s own orchestration, never a
    bare CLI flag) are responsible for having already confirmed
    `verify_ingested` and `verify_roundtrip` both passed and the file is
    age- and agent-gated; this function performs no gating of its own --
    it only performs the compression, verification, and swap once called.
    """
    if not file_path.is_file():
        raise FileNotFoundError(f"cannot archive missing file: {file_path}")

    archived_path = file_path.with_name(file_path.name + ".zst")
    if archived_path.exists():
        raise FileExistsError(f"archive target already exists: {archived_path}")

    original_hash = _sha256_file(file_path)
    content_sha256, _stored_sha256, _stored_size = compress_file(
        file_path, archived_path, level=compression_level
    )
    if content_sha256 != original_hash:
        archived_path.unlink(missing_ok=True)
        raise RuntimeError(f"compression content hash mismatch for {file_path}; original left untouched")

    with tempfile.TemporaryDirectory(prefix="searchat-archive-verify-") as tmp_dir:
        decompressed_path = Path(tmp_dir) / file_path.name
        decompress_file(archived_path, decompressed_path)
        if _sha256_file(decompressed_path) != original_hash:
            archived_path.unlink(missing_ok=True)
            raise RuntimeError(f"decompression verification failed for {file_path}; original left untouched")

    file_path.unlink()
    return archived_path

