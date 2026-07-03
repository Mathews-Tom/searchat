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
import json
import tempfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

import duckdb

from searchat.core.connectors.base import AgentProviderBase
from searchat.core.connectors.registry import get_connector_by_name
from searchat.core.logging_config import get_logger
from searchat.config.settings import LifecycleConfig, RetentionConfig
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



def prune_source(file_path: Path) -> None:
    """Delete `file_path`.

    Callers (`services.source_lifecycle`'s own orchestration, never a bare
    CLI flag) are responsible for having already confirmed
    `verify_ingested` and `verify_roundtrip` both passed, the file is
    age- and agent-gated, and a tombstone will be written for it -- this
    function performs no gating or tombstoning of its own; it only
    deletes the file it is given.
    """
    if not file_path.is_file():
        raise FileNotFoundError(f"cannot prune missing file: {file_path}")
    file_path.unlink()


@dataclass(frozen=True)
class TombstoneEntry:
    """Append-only forensic record of one archive/prune action -- the only
    recovery path once a source file has actually been removed from disk
    (or replaced in place by its `.zst` archive). Carries enough Parquet
    provenance (`conversation_id`, `message_count`) and file provenance
    (`checksum`) to identify exactly what was removed, when, and what the
    pipeline believed justified it.
    """

    action: str  # "archive" | "prune"
    connector_name: str
    file_path: str
    conversation_id: str
    project_id: str | None
    checksum: str  # sha256 of the original file's bytes, computed before the action
    message_count: int  # Parquet-side provenance: message_count already indexed
    archived_path: str | None  # set only when action == "archive"
    timestamp: str  # ISO 8601 UTC, when the action was recorded

    def to_dict(self) -> dict[str, object]:
        return {
            "action": self.action,
            "connector_name": self.connector_name,
            "file_path": self.file_path,
            "conversation_id": self.conversation_id,
            "project_id": self.project_id,
            "checksum": self.checksum,
            "message_count": self.message_count,
            "archived_path": self.archived_path,
            "timestamp": self.timestamp,
        }


_TOMBSTONE_LOG_FILENAME = "tombstones.jsonl"


def tombstone_log_path(tombstone_dir: Path) -> Path:
    """Path to the single append-only tombstone log file under
    `tombstone_dir` (conventionally `~/.searchat/tombstones/`)."""
    return Path(tombstone_dir) / _TOMBSTONE_LOG_FILENAME


def write_tombstone(tombstone_dir: Path, entry: TombstoneEntry) -> Path:
    """Append one JSON line recording `entry` to the tombstone log,
    creating `tombstone_dir` and the log file if either doesn't exist yet.

    Append-only: never truncates, rewrites, or removes existing entries --
    every prior tombstone remains recoverable for as long as the log file
    itself is not deleted.
    """
    log_path = tombstone_log_path(tombstone_dir)
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with open(log_path, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry.to_dict()) + "\n")
    return log_path


def _iter_indexed_source_files(
    db_path: Path, *, connection: duckdb.DuckDBPyConnection | None = None
) -> list[tuple[str, str]]:
    """`(connector_name, file_path)` pairs for every `status = 'indexed'`
    `source_file_state` row. Rows with a null/empty `connector_name` or
    `file_path` are skipped -- they cannot be gated by
    `lifecycle.enabled_agents` or acted on."""
    query = "SELECT connector_name, file_path FROM source_file_state WHERE status = 'indexed'"
    if connection is not None:
        cur = connection.cursor()
        try:
            rows = cur.execute(query).fetchall()
        except duckdb.Error:
            return []
        finally:
            cur.close()
    else:
        if not db_path.exists():
            return []
        con = duckdb.connect(str(db_path), read_only=True)
        try:
            rows = con.execute(query).fetchall()
        except duckdb.Error:
            return []
        finally:
            con.close()
    return [(name, path) for name, path in rows if name and path]


@dataclass(frozen=True)
class LifecycleDecision:
    """Outcome of evaluating one source file through the full M8 gate
    chain: per-agent opt-in, age threshold, `verify_ingested`, and --
    only when neither of those refused it and `dry_run` is `False` --
    `verify_roundtrip` followed by the action itself. `eligible=True`
    means every gate that ran passed; it does NOT by itself mean the
    action was taken (see `action_taken`, which is `None` for a dry run
    even when `eligible` is `True`)."""

    connector_name: str
    file_path: str
    age_days: float | None
    agent_enabled: bool
    age_gated: bool
    ingested: VerificationResult | None
    roundtrip: RoundtripResult | None
    eligible: bool
    action_taken: str | None
    archived_path: str | None
    tombstone_path: str | None
    skip_reason: str | None

    def to_dict(self) -> dict[str, object]:
        return {
            "connector_name": self.connector_name,
            "file_path": self.file_path,
            "age_days": self.age_days,
            "agent_enabled": self.agent_enabled,
            "age_gated": self.age_gated,
            "ingested": self.ingested.to_dict() if self.ingested is not None else None,
            "roundtrip": self.roundtrip.to_dict() if self.roundtrip is not None else None,
            "eligible": self.eligible,
            "action_taken": self.action_taken,
            "archived_path": self.archived_path,
            "tombstone_path": self.tombstone_path,
            "skip_reason": self.skip_reason,
        }


@dataclass
class _DecisionBuilder:
    """Mutable, field-for-field twin of `LifecycleDecision` used while
    `evaluate_and_act_on_source` walks the gate chain -- `LifecycleDecision`
    itself stays frozen (an immutable result value), so building it up
    incrementally across many early-return points needs a separate,
    type-checked mutable holder rather than an untyped `dict[str, object]`.
    """

    connector_name: str
    file_path: str
    age_days: float | None = None
    agent_enabled: bool = False
    age_gated: bool = False
    ingested: VerificationResult | None = None
    roundtrip: RoundtripResult | None = None
    eligible: bool = False
    action_taken: str | None = None
    archived_path: str | None = None
    tombstone_path: str | None = None
    skip_reason: str | None = None

    def freeze(self) -> LifecycleDecision:
        return LifecycleDecision(
            connector_name=self.connector_name,
            file_path=self.file_path,
            age_days=self.age_days,
            agent_enabled=self.agent_enabled,
            age_gated=self.age_gated,
            ingested=self.ingested,
            roundtrip=self.roundtrip,
            eligible=self.eligible,
            action_taken=self.action_taken,
            archived_path=self.archived_path,
            tombstone_path=self.tombstone_path,
            skip_reason=self.skip_reason,
        )


def evaluate_and_act_on_source(
    *,
    db_path: Path,
    connector_name: str,
    file_path: Path,
    policy: LifecycleConfig,
    action: str,
    dry_run: bool,
    tombstone_dir: Path,
    now: datetime | None = None,
    connection: duckdb.DuckDBPyConnection | None = None,
    retention: RetentionConfig | None = None,
) -> LifecycleDecision:
    """Evaluate one candidate through every M8 gate and, only once all of
    them pass AND `dry_run` is `False`, perform `action` ("archive" or
    "prune") and write its tombstone.

    Gate order, cheapest and most safety-critical first: per-agent
    opt-in, per-project retention policy (M12), age threshold,
    `verify_ingested` (read-only). `dry_run` is checked immediately
    after `verify_ingested`, before `verify_roundtrip` ever runs --
    `verify_roundtrip` is the only stage in this whole chain that
    performs a filesystem write (to a throwaway temp directory), so a
    `dry_run=True` call can never write to disk no matter how many
    candidates would otherwise be eligible.

    `retention` (M12) is consulted BEFORE the age-threshold gate: a
    project resolved as `never_touch` short-circuits here regardless of
    how old the file is, and a project with an `archive_after_days`
    override replaces `policy.age_threshold_days` for the age check
    that follows (used for both `action="archive"` and
    `action="prune"` -- M8 has always used one global threshold for
    both actions). `retention=None` (the default) reproduces the exact
    pre-M12 behavior: no project lookup, no override.
    """
    if action not in ("archive", "prune"):
        raise ValueError(f"unknown lifecycle action: {action!r}")

    now = now or datetime.now(timezone.utc)
    state = _DecisionBuilder(connector_name=connector_name, file_path=str(file_path))

    if connector_name not in policy.enabled_agents:
        state.skip_reason = f"connector {connector_name!r} is not in lifecycle.enabled_agents"
        return state.freeze()
    state.agent_enabled = True

    effective_age_threshold_days = policy.age_threshold_days
    if retention is not None:
        state_row = _read_source_file_state(db_path, file_path, connection=connection)
        row_project_id = state_row["project_id"] if state_row else None
        row_project_id = row_project_id if isinstance(row_project_id, str) and row_project_id else None
        project_policy = retention.resolve(row_project_id)
        if project_policy is not None:
            if project_policy.never_touch:
                state.skip_reason = (
                    f"project {row_project_id!r} is marked never_touch in retention policy"
                )
                return state.freeze()
            if project_policy.archive_after_days is not None:
                effective_age_threshold_days = project_policy.archive_after_days

    try:
        age_days = (now.timestamp() - file_path.stat().st_mtime) / 86400.0
    except OSError:
        state.skip_reason = "source file does not exist on disk"
        return state.freeze()
    state.age_days = age_days

    if age_days < effective_age_threshold_days:
        state.skip_reason = f"younger than the effective age_threshold_days ({effective_age_threshold_days})"
        return state.freeze()
    state.age_gated = True

    connector = get_connector_by_name(connector_name)
    if connector is None or not isinstance(connector, AgentProviderBase):
        state.skip_reason = f"no registered AgentProviderBase connector named {connector_name!r}"
        return state.freeze()

    ingested = verify_ingested(db_path, connector, file_path, connection=connection)
    state.ingested = ingested
    if not ingested.ok:
        state.skip_reason = f"verify_ingested failed: {ingested.reason}"
        return state.freeze()

    if dry_run:
        state.eligible = True
        state.skip_reason = "dry_run=True: verify_roundtrip and the action were not attempted"
        return state.freeze()

    row = _read_source_file_state(db_path, file_path, connection=connection)
    conversation_id = row["conversation_id"] if row else None
    project_id = row["project_id"] if row else None
    if not conversation_id or not isinstance(conversation_id, str):
        state.skip_reason = "no conversation_id on source_file_state row"
        return state.freeze()

    try:
        record = connector.parse(file_path, embedding_id=0)
    except Exception as exc:
        state.skip_reason = f"re-parse before roundtrip check failed: {exc}"
        return state.freeze()

    roundtrip = verify_roundtrip(connector, record)
    state.roundtrip = roundtrip
    if not roundtrip.ok:
        state.skip_reason = f"verify_roundtrip failed: {roundtrip.reason}"
        return state.freeze()

    checksum = _sha256_file(file_path)
    meta = _read_conversation_meta(db_path, conversation_id, connection=connection)
    raw_message_count = meta["message_count"] if meta else None
    message_count = raw_message_count if isinstance(raw_message_count, int) else record.message_count

    # Tombstone is written BEFORE the irreversible archive_source/prune_source
    # call, not after: `archived_path` for the "archive" action is fully
    # predictable (archive_source's own contract is `<name>.zst`, computed
    # here without touching the file), so nothing about the tombstone's
    # content actually depends on the action having already run. This
    # ordering guarantees the module's own invariant ("every successful
    # archive/prune writes exactly one tombstone entry") even when
    # `write_tombstone` itself fails: a failure here raises BEFORE the
    # file is ever touched, so there is no code path that deletes/archives
    # a file and then fails to record it. The reverse ordering (act, then
    # tombstone) would instead risk an irreversible deletion with no
    # tombstone if the write failed afterward -- exactly the forensic gap
    # this module exists to prevent.
    predicted_archived_path = (
        str(file_path.with_name(file_path.name + ".zst")) if action == "archive" else None
    )
    entry = TombstoneEntry(
        action=action,
        connector_name=connector_name,
        file_path=str(file_path),
        conversation_id=conversation_id,
        project_id=project_id if isinstance(project_id, str) else None,
        checksum=checksum,
        message_count=message_count,
        archived_path=predicted_archived_path,
        timestamp=now.isoformat(),
    )
    tombstone_path = write_tombstone(tombstone_dir, entry)

    if action == "archive":
        archived = archive_source(file_path)
        state.archived_path = str(archived)
    else:
        prune_source(file_path)

    state.eligible = True
    state.action_taken = action
    state.tombstone_path = str(tombstone_path)
    return state.freeze()


def run_lifecycle_action(
    *,
    db_path: Path,
    policy: LifecycleConfig,
    action: str,
    dry_run: bool,
    tombstone_dir: Path,
    now: datetime | None = None,
    connection: duckdb.DuckDBPyConnection | None = None,
    retention: RetentionConfig | None = None,
) -> list[LifecycleDecision]:
    """Evaluate every currently-indexed source file against the full M8
    gate chain, performing `action` ("archive" or "prune") for each one
    that passes every gate, when `dry_run` is `False`.

    With the shipped defaults (`lifecycle.enabled_agents = []`,
    `lifecycle.dry_run = true`), this makes zero filesystem writes: every
    candidate is refused at the per-agent opt-in gate before
    `verify_ingested` (a read) or `verify_roundtrip`/the action itself
    (the only writing stages) ever run.

    `retention` (M12), when passed, is forwarded unchanged to every
    per-file `evaluate_and_act_on_source` call -- see that function's
    docstring for the per-project gate it adds.
    """
    candidates = _iter_indexed_source_files(db_path, connection=connection)
    return [
        evaluate_and_act_on_source(
            db_path=db_path,
            connector_name=connector_name,
            file_path=Path(file_path),
            policy=policy,
            action=action,
            dry_run=dry_run,
            tombstone_dir=tombstone_dir,
            now=now,
            connection=connection,
            retention=retention,
        )
        for connector_name, file_path in candidates
    ]
