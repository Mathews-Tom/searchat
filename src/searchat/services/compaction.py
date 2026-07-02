"""Safe copy-compaction for the DuckDB store.

DuckDB files never shrink in place: long-running append/checkpoint
workloads leave dead blocks behind that only a copy-compaction reclaims.
This module implements the checkpoint -> attach -> COPY FROM DATABASE ->
verify -> atomic-rename sequence documented as the Tier 0 manual recovery
procedure in `.docs/searchat-memory-management-enhancement-analysis.md`
Appendix A, and as the managed `duckdb-copy-compact` skill, so it can run
unattended via `searchat compact` (M3).

Every extension backing an index (vss, fts) is loaded, and HNSW
persistence enabled, on every connection BEFORE any write op. Skipping
this can make CHECKPOINT / COPY FROM DATABASE fail with FATAL "unknown
index type 'HNSW'" when the on-disk catalog references an index whose
extension has not been loaded in this connection yet -- the failure
observed during the Tier 0 recovery. A FATAL error aborts the DuckDB
process outright and no Python `except` clause can catch it -- callers
that must survive that failure mode isolate `compact_database` in a
subprocess so a FATAL there can never take down the parent process or
leave the original file half-written.

`compact_database` never mutates `db_path` until `verify_compaction` has
proven the compacted copy is query-identical: same row counts across
every schema (main + fts_main_*), the same index set, matching
`match_bm25` and `array_cosine_distance` functional probes, and a
zero-row symmetric diff on `conversations`.
"""
from __future__ import annotations

import logging
import re
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

import duckdb

from searchat.storage.schema import install_fts, install_vss

log = logging.getLogger(__name__)

_PROBE_WORD_RE = re.compile(r"[A-Za-z]{4,}")

# Restricted to `main` + `fts_main_*`, matching the scope
# `services/storage_health.py::estimate_live_data_size` already verifies.
_BASE_TABLES_SQL = (
    "SELECT table_schema, table_name FROM information_schema.tables "
    "WHERE table_catalog = ? AND table_type = 'BASE TABLE' "
    "AND (table_schema = 'main' OR table_schema LIKE 'fts_main_%') "
    "ORDER BY 1, 2"
)


@dataclass(frozen=True)
class VerificationResult:
    """Verdict from comparing a compacted copy against its source.

    Mirrors Appendix A's manual verification: row counts, index set,
    functional FTS + vector probes, and a symmetric-diff spot-check.
    `fts_probe_match`/`vector_probe_match` are `None` when there was
    nothing to probe (empty exchanges/embeddings) rather than `False`.
    """

    passed: bool
    row_counts_match: bool
    index_names_match: bool
    fts_probe_match: bool | None
    vector_probe_match: bool | None
    symmetric_diff_match: bool
    mismatches: tuple[str, ...]


@dataclass(frozen=True)
class CompactionResult:
    """Outcome of a `compact_database` run.

    `success=False` always means `original_path` was never modified --
    the compacted copy (and any quarantined leftovers) live at other
    paths, never in place of the original, until every check passes.
    """

    success: bool
    original_path: Path
    original_size_bytes: int
    compacted_size_bytes: int
    bytes_reclaimed: int
    preserved_original_path: Path | None
    quarantined_path: Path | None
    verification: VerificationResult | None
    error: str | None
    duration_seconds: float


def _sql_literal(path: Path) -> str:
    """Quote a filesystem path as a DuckDB SQL string literal.

    ATTACH does not support bound parameters for its path argument, so the
    path is escaped by doubling embedded single quotes (standard SQL
    literal escaping) instead.
    """
    return "'" + str(path).replace("'", "''") + "'"


def _quote_ident(name: str) -> str:
    return '"' + name.replace('"', '""') + '"'


def _prepare_connection(conn: duckdb.DuckDBPyConnection) -> None:
    """Load every extension backing an index before any write op.

    Mirrors `UnifiedStorage.__init__` (storage/unified_storage.py) so a
    compaction connection sees the catalog exactly as the live app does.
    """
    install_vss(conn)
    install_fts(conn)
    try:
        conn.execute("SET hnsw_enable_experimental_persistence = true")
    except duckdb.Error:
        pass


def _scalar(con: duckdb.DuckDBPyConnection, sql: str, params: list | None = None) -> int:
    """Run a query guaranteed to return exactly one row with one integer
    column (e.g. `SELECT COUNT(*)`) and return that value.
    """
    row = con.execute(sql, params or []).fetchone()
    assert row is not None, f"expected exactly one row from: {sql}"
    return int(row[0])


def _table_row_counts(con: duckdb.DuckDBPyConnection, catalog: str) -> dict[tuple[str, str], int]:
    tables = con.execute(_BASE_TABLES_SQL, [catalog]).fetchall()
    counts: dict[tuple[str, str], int] = {}
    for schema, table in tables:
        qualified = f"{_quote_ident(catalog)}.{_quote_ident(schema)}.{_quote_ident(table)}"
        counts[(schema, table)] = _scalar(con, f"SELECT COUNT(*) FROM {qualified}")
    return counts


def _index_names(con: duckdb.DuckDBPyConnection, catalog: str) -> set[tuple[str, str, str]]:
    rows = con.execute(
        "SELECT schema_name, index_name, table_name FROM duckdb_indexes() WHERE database_name = ?",
        [catalog],
    ).fetchall()
    return {(schema, name, table) for schema, name, table in rows}


def _fts_probe(src_path: Path, dst_path: Path, mismatches: list[str]) -> bool | None:
    """Functional BM25 probe: pick a real exchange from `src`, search both
    sides for a word drawn from its own text, and require identical hits.

    Each side is queried on its OWN direct connection rather than through a
    shared ATTACH: `match_bm25`'s generated macro resolves its internal
    helper tables (`stats`, `dict`, ...) against the connection's *current*
    catalog, not the catalog its call was schema-qualified from -- querying
    `dst.fts_main_exchanges.match_bm25(...)` while `src` is the current
    catalog silently scores against `src`'s own FTS state, which would
    mask a real difference in `dst`.

    Returns `None` (not applicable) when there is no FTS index to probe.
    """
    src_con = duckdb.connect(str(src_path), read_only=True)
    try:
        _prepare_connection(src_con)
        has_fts = _scalar(
            src_con,
            "SELECT COUNT(*) FROM information_schema.tables "
            "WHERE table_schema = 'fts_main_exchanges' AND table_name = 'terms'",
        )
        if not has_fts:
            return None
        row = src_con.execute(
            "SELECT exchange_text FROM exchanges WHERE exchange_text IS NOT NULL "
            "ORDER BY exchange_id LIMIT 1"
        ).fetchone()
        if row is None:
            return None
        term: str | None = None
        src_hits: list[tuple] = []
        for candidate in _PROBE_WORD_RE.findall(row[0] or ""):
            hits = src_con.execute(
                "SELECT exchange_id, fts_main_exchanges.match_bm25(exchange_id, ?) AS score "
                "FROM exchanges WHERE score IS NOT NULL ORDER BY score DESC, exchange_id",
                [candidate],
            ).fetchall()
            if hits:
                term = candidate
                src_hits = hits
                break
    finally:
        src_con.close()

    if term is None:
        # Every candidate word in the sample text was filtered (stopword,
        # below the FTS minimum length, etc.) -- nothing usable to probe.
        return None

    dst_con = duckdb.connect(str(dst_path), read_only=True)
    try:
        _prepare_connection(dst_con)
        dst_hits = dst_con.execute(
            "SELECT exchange_id, fts_main_exchanges.match_bm25(exchange_id, ?) AS score "
            "FROM exchanges WHERE score IS NOT NULL ORDER BY score DESC, exchange_id",
            [term],
        ).fetchall()
    finally:
        dst_con.close()

    ok = src_hits == dst_hits
    if not ok:
        mismatches.append(f"FTS probe mismatch for term {term!r}: src={src_hits} dst={dst_hits}")
    return ok


def _vector_probe(con: duckdb.DuckDBPyConnection, mismatches: list[str]) -> bool | None:
    """Functional HNSW probe: fetch one real embedding from `src` and require
    identical nearest-neighbor rankings on both sides.

    Returns `None` (not applicable) when there are no embeddings to probe.
    """
    probe = con.execute(
        "SELECT exchange_id, embedding FROM src.verbatim_embeddings ORDER BY exchange_id LIMIT 1"
    ).fetchone()
    if probe is None:
        return None
    dim = len(probe[1])
    src_neighbors = con.execute(
        f"SELECT exchange_id, round(array_cosine_distance(embedding, ?::FLOAT[{dim}]), 6) AS dist "
        "FROM src.verbatim_embeddings ORDER BY dist, exchange_id LIMIT 10",
        [probe[1]],
    ).fetchall()
    dst_neighbors = con.execute(
        f"SELECT exchange_id, round(array_cosine_distance(embedding, ?::FLOAT[{dim}]), 6) AS dist "
        "FROM dst.verbatim_embeddings ORDER BY dist, exchange_id LIMIT 10",
        [probe[1]],
    ).fetchall()
    ok = bool(src_neighbors) and src_neighbors == dst_neighbors
    if not ok:
        mismatches.append(f"vector probe mismatch: src={src_neighbors} dst={dst_neighbors}")
    return ok


def _symmetric_diff(con: duckdb.DuckDBPyConnection, mismatches: list[str]) -> bool:
    """Spot-check a zero-row symmetric diff on `conversations`, matching
    Appendix A's final verification step."""
    has_table = _scalar(
        con,
        "SELECT COUNT(*) FROM information_schema.tables WHERE table_catalog IN ('src', 'dst') "
        "AND table_schema = 'main' AND table_name = 'conversations'",
    )
    if has_table < 2:
        return True
    forward = _scalar(
        con, "SELECT COUNT(*) FROM (SELECT * FROM src.conversations EXCEPT SELECT * FROM dst.conversations)"
    )
    backward = _scalar(
        con, "SELECT COUNT(*) FROM (SELECT * FROM dst.conversations EXCEPT SELECT * FROM src.conversations)"
    )
    ok = forward == 0 and backward == 0
    if not ok:
        mismatches.append(f"conversations symmetric diff nonzero: forward={forward} backward={backward}")
    return ok


def verify_compaction(src_path: Path, dst_path: Path) -> VerificationResult:
    """Verify `dst_path` is query-identical to `src_path`.

    Reuses M1's row-count/index verification pattern
    (`services/storage_health.py`) and extends it with the functional FTS
    + vector probes and symmetric-diff spot-check from Appendix A. Opens
    both files read-only; never mutates either.
    """
    mismatches: list[str] = []
    con = duckdb.connect()
    try:
        _prepare_connection(con)
        con.execute(f"ATTACH {_sql_literal(src_path)} AS src (READ_ONLY)")
        con.execute(f"ATTACH {_sql_literal(dst_path)} AS dst (READ_ONLY)")

        src_counts = _table_row_counts(con, "src")
        dst_counts = _table_row_counts(con, "dst")
        row_counts_match = src_counts == dst_counts
        if not row_counts_match:
            mismatches.append(f"table row counts differ: src={src_counts} dst={dst_counts}")

        src_indexes = _index_names(con, "src")
        dst_indexes = _index_names(con, "dst")
        index_names_match = src_indexes == dst_indexes
        if not index_names_match:
            mismatches.append(f"index set differs: src={src_indexes} dst={dst_indexes}")

        fts_probe_match = _fts_probe(src_path, dst_path, mismatches)
        vector_probe_match = _vector_probe(con, mismatches)
        symmetric_diff_match = _symmetric_diff(con, mismatches)
    finally:
        con.close()

    passed = (
        row_counts_match
        and index_names_match
        and fts_probe_match is not False
        and vector_probe_match is not False
        and symmetric_diff_match
    )
    return VerificationResult(
        passed=passed,
        row_counts_match=row_counts_match,
        index_names_match=index_names_match,
        fts_probe_match=fts_probe_match,
        vector_probe_match=vector_probe_match,
        symmetric_diff_match=symmetric_diff_match,
        mismatches=tuple(mismatches),
    )


def _copy_compact(src_path: Path, dst_path: Path) -> None:
    """Checkpoint -> attach -> COPY FROM DATABASE -> checkpoint.

    Only merges `src_path`'s own WAL into itself; never writes anything
    else to it. `dst_path` is a fresh sibling file the caller cleans up on
    failure.
    """
    checkpoint_con = duckdb.connect(str(src_path))
    try:
        _prepare_connection(checkpoint_con)
        checkpoint_con.execute("CHECKPOINT")
    finally:
        checkpoint_con.close()

    copy_con = duckdb.connect()
    try:
        _prepare_connection(copy_con)
        copy_con.execute(f"ATTACH {_sql_literal(src_path)} AS s (READ_ONLY)")
        copy_con.execute(f"ATTACH {_sql_literal(dst_path)} AS d")
        copy_con.execute("COPY FROM DATABASE s TO d")
        copy_con.execute("USE d")
        copy_con.execute("CHECKPOINT")
    finally:
        copy_con.close()


def _temp_dest_path(db_path: Path) -> Path:
    return db_path.with_name(db_path.name + ".compact-tmp")


def _stamped_sibling(db_path: Path, label: str, *, now: datetime | None = None) -> Path:
    stamp = (now or datetime.now(timezone.utc)).strftime("%Y%m%dT%H%M%SZ")
    return db_path.with_name(f"{db_path.name}.{label}-{stamp}")


def _unlink_with_wal(path: Path) -> None:
    path.unlink(missing_ok=True)
    Path(str(path) + ".wal").unlink(missing_ok=True)


def _post_swap_smoke_test(db_path: Path) -> bool:
    """Confirm the newly swapped-in file actually opens and its catalog is
    readable before deleting the preserved original."""
    try:
        con = duckdb.connect(str(db_path), read_only=True)
        try:
            _prepare_connection(con)
            con.execute("SELECT COUNT(*) FROM information_schema.tables").fetchone()
        finally:
            con.close()
        return True
    except duckdb.Error as exc:
        log.error("Post-swap smoke test failed for %s: %s", db_path, exc)
        return False


def compact_database(db_path: Path) -> CompactionResult:
    """Reclaim dead blocks in `db_path` via verified copy-compaction.

    `db_path` is never mutated until `verify_compaction` proves the
    compacted copy is query-identical, and the pre-compaction original is
    kept alongside as `<name>.pre-compact-<timestamp>` until a post-swap
    smoke test on the new file also passes -- only then is it removed. Any
    failure at any stage leaves `db_path` exactly as it was before the
    call.
    """
    start = time.perf_counter()
    db_path = Path(db_path)

    if not db_path.exists():
        return CompactionResult(
            success=False,
            original_path=db_path,
            original_size_bytes=0,
            compacted_size_bytes=0,
            bytes_reclaimed=0,
            preserved_original_path=None,
            quarantined_path=None,
            verification=None,
            error=f"No database found at {db_path}",
            duration_seconds=time.perf_counter() - start,
        )

    original_size = db_path.stat().st_size
    dst_path = _temp_dest_path(db_path)
    _unlink_with_wal(dst_path)

    try:
        _copy_compact(db_path, dst_path)
    except duckdb.IOException as exc:
        _unlink_with_wal(dst_path)
        return CompactionResult(
            success=False,
            original_path=db_path,
            original_size_bytes=original_size,
            compacted_size_bytes=0,
            bytes_reclaimed=0,
            preserved_original_path=None,
            quarantined_path=None,
            verification=None,
            error=f"Database is in use by another process; refusing to compact: {exc}",
            duration_seconds=time.perf_counter() - start,
        )
    except Exception as exc:  # noqa: BLE001 - any failure here must leave db_path untouched
        _unlink_with_wal(dst_path)
        return CompactionResult(
            success=False,
            original_path=db_path,
            original_size_bytes=original_size,
            compacted_size_bytes=0,
            bytes_reclaimed=0,
            preserved_original_path=None,
            quarantined_path=None,
            verification=None,
            error=f"Copy-compaction failed: {exc}",
            duration_seconds=time.perf_counter() - start,
        )

    verification = verify_compaction(db_path, dst_path)
    if not verification.passed:
        dst_size = dst_path.stat().st_size if dst_path.exists() else 0
        _unlink_with_wal(dst_path)
        return CompactionResult(
            success=False,
            original_path=db_path,
            original_size_bytes=original_size,
            compacted_size_bytes=dst_size,
            bytes_reclaimed=0,
            preserved_original_path=None,
            quarantined_path=None,
            verification=verification,
            error=f"Verification failed: {'; '.join(verification.mismatches)}",
            duration_seconds=time.perf_counter() - start,
        )

    preserved_path = _stamped_sibling(db_path, "pre-compact")
    db_path.rename(preserved_path)
    dst_path.rename(db_path)

    if not _post_swap_smoke_test(db_path):
        # Roll back: quarantine the broken swap-in, restore the preserved
        # original. preserved_path no longer exists once this rename
        # completes -- the original is back at db_path, not "preserved"
        # separately -- so preserved_original_path is None here;
        # quarantined_path points at the broken copy for forensics.
        broken_path = _stamped_sibling(db_path, "post-swap-failed")
        _unlink_with_wal(broken_path)
        broken_size = db_path.stat().st_size
        db_path.rename(broken_path)
        preserved_path.rename(db_path)
        return CompactionResult(
            success=False,
            original_path=db_path,
            original_size_bytes=original_size,
            compacted_size_bytes=broken_size,
            bytes_reclaimed=0,
            preserved_original_path=None,
            quarantined_path=broken_path,
            verification=verification,
            error=(
                "Post-swap smoke test failed; original restored, broken copy "
                f"quarantined at {broken_path}"
            ),
            duration_seconds=time.perf_counter() - start,
        )

    _unlink_with_wal(preserved_path)
    compacted_size = db_path.stat().st_size
    return CompactionResult(
        success=True,
        original_path=db_path,
        original_size_bytes=original_size,
        compacted_size_bytes=compacted_size,
        bytes_reclaimed=max(original_size - compacted_size, 0),
        preserved_original_path=None,
        quarantined_path=None,
        verification=verification,
        error=None,
        duration_seconds=time.perf_counter() - start,
    )
