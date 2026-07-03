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
from dataclasses import dataclass
from pathlib import Path

import duckdb

from searchat.core.connectors.base import AgentProviderBase
from searchat.core.logging_config import get_logger

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
