"""Unit tests for services/compaction.py -- verified copy-compaction engine."""
from __future__ import annotations

import hashlib
import multiprocessing
import queue
import subprocess
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch

import duckdb
import numpy as np

from searchat.config import Config
from searchat.core.unified_indexer import UnifiedIndexer
from searchat.services import compaction as comp
from searchat.services.compaction import (
    VerificationResult,
    _prepare_connection,
    compact_database,
    verify_compaction,
)
from searchat.services.storage_health import compute_bloat_ratio, estimate_live_data_size, inspect_database_size
from searchat.storage.unified_storage import UnifiedStorage


# ---------------------------------------------------------------------------
# Hand-built fixture DBs for verify_compaction unit tests
# ---------------------------------------------------------------------------


def _seed_minimal_db(db_path: Path, *, rows: tuple[tuple[str, str, list[float]], ...]) -> None:
    con = duckdb.connect(str(db_path))
    _prepare_connection(con)
    con.execute("CREATE TABLE exchanges(exchange_id VARCHAR PRIMARY KEY, exchange_text VARCHAR)")
    con.execute("CREATE TABLE verbatim_embeddings(exchange_id VARCHAR PRIMARY KEY, embedding FLOAT[4])")
    for exchange_id, text, vector in rows:
        con.execute("INSERT INTO exchanges VALUES (?, ?)", [exchange_id, text])
        con.execute("INSERT INTO verbatim_embeddings VALUES (?, ?)", [exchange_id, vector])
    con.execute(
        "PRAGMA create_fts_index('exchanges', 'exchange_id', 'exchange_text', "
        "stemmer = 'porter', stopwords = 'english', overwrite = 1)"
    )
    con.execute("CREATE INDEX verbatim_hnsw ON verbatim_embeddings USING HNSW (embedding) WITH (metric = 'cosine')")
    con.execute("CHECKPOINT")
    con.close()


_FIXTURE_ROWS = (
    ("e1", "hello world sorting lists", [1.0, 0.0, 0.0, 0.0]),
    ("e2", "python reverse sorted arrays", [0.0, 1.0, 0.0, 0.0]),
)


class TestVerifyCompaction:
    def test_identical_copy_passes_every_check(self, tmp_path: Path) -> None:
        src = tmp_path / "src.duckdb"
        dst = tmp_path / "dst.duckdb"
        _seed_minimal_db(src, rows=_FIXTURE_ROWS)
        _seed_minimal_db(dst, rows=_FIXTURE_ROWS)

        result = verify_compaction(src, dst)

        assert result.passed is True
        assert result.row_counts_match is True
        assert result.index_names_match is True
        assert result.fts_probe_match is True
        assert result.vector_probe_match is True
        assert result.symmetric_diff_match is True
        assert result.mismatches == ()

    def test_row_count_mismatch_fails(self, tmp_path: Path) -> None:
        src = tmp_path / "src.duckdb"
        dst = tmp_path / "dst.duckdb"
        _seed_minimal_db(src, rows=_FIXTURE_ROWS)
        _seed_minimal_db(dst, rows=_FIXTURE_ROWS[:1])

        result = verify_compaction(src, dst)

        assert result.passed is False
        assert result.row_counts_match is False
        assert any("row counts differ" in m for m in result.mismatches)

    def test_missing_index_fails(self, tmp_path: Path) -> None:
        src = tmp_path / "src.duckdb"
        dst = tmp_path / "dst.duckdb"
        _seed_minimal_db(src, rows=_FIXTURE_ROWS)
        _seed_minimal_db(dst, rows=_FIXTURE_ROWS)

        con = duckdb.connect(str(dst))
        _prepare_connection(con)
        con.execute("DROP INDEX verbatim_hnsw")
        con.execute("CHECKPOINT")
        con.close()

        result = verify_compaction(src, dst)

        assert result.passed is False
        assert result.index_names_match is False

    def test_fts_probe_mismatch_fails(self, tmp_path: Path) -> None:
        """Corrupt dst's FTS document length (affects BM25 scoring) without
        touching any table's row count, so this is isolated to the FTS
        probe rather than also tripping the row-count check."""
        src = tmp_path / "src.duckdb"
        dst = tmp_path / "dst.duckdb"
        _seed_minimal_db(src, rows=_FIXTURE_ROWS)
        _seed_minimal_db(dst, rows=_FIXTURE_ROWS)

        con = duckdb.connect(str(dst))
        _prepare_connection(con)
        con.execute("UPDATE fts_main_exchanges.docs SET len = len * 100 WHERE name = 'e1'")
        con.execute("CHECKPOINT")
        con.close()

        result = verify_compaction(src, dst)

        assert result.row_counts_match is True
        assert result.passed is False
        assert result.fts_probe_match is False

    def test_vector_probe_mismatch_fails(self, tmp_path: Path) -> None:
        src = tmp_path / "src.duckdb"
        dst = tmp_path / "dst.duckdb"
        _seed_minimal_db(src, rows=_FIXTURE_ROWS)
        _seed_minimal_db(
            dst,
            rows=(
                ("e1", "hello world sorting lists", [0.0, 0.0, 1.0, 0.0]),
                ("e2", "python reverse sorted arrays", [0.0, 1.0, 0.0, 0.0]),
            ),
        )

        result = verify_compaction(src, dst)

        assert result.passed is False
        assert result.vector_probe_match is False

    def test_empty_tables_probes_are_not_applicable(self, tmp_path: Path) -> None:
        src = tmp_path / "src.duckdb"
        dst = tmp_path / "dst.duckdb"
        _seed_minimal_db(src, rows=())
        _seed_minimal_db(dst, rows=())

        result = verify_compaction(src, dst)

        assert result.passed is True
        assert result.fts_probe_match is None
        assert result.vector_probe_match is None

    def test_symmetric_diff_detects_conversations_divergence(self, tmp_path: Path) -> None:
        """Equal row counts alone must not be mistaken for identical
        content: dst's conversations table here has the same row count as
        src but a genuinely different row, which only the symmetric-diff
        spot-check (not row_counts_match) can catch."""
        src = tmp_path / "src.duckdb"
        dst = tmp_path / "dst.duckdb"

        def _seed_conversations(path: Path, conversation_id: str) -> None:
            _seed_minimal_db(path, rows=())
            con = duckdb.connect(str(path))
            _prepare_connection(con)
            con.execute("CREATE TABLE conversations(id VARCHAR PRIMARY KEY, title VARCHAR)")
            con.execute("INSERT INTO conversations VALUES (?, 'title')", [conversation_id])
            con.execute("CHECKPOINT")
            con.close()

        _seed_conversations(src, "conv-a")
        _seed_conversations(dst, "conv-b")

        result = verify_compaction(src, dst)

        assert result.row_counts_match is True
        assert result.symmetric_diff_match is False
        assert result.passed is False
        assert any("symmetric diff" in m for m in result.mismatches)


# ---------------------------------------------------------------------------
# Real, indexed conversation DB with synthetic bloat -- end-to-end engine tests
# ---------------------------------------------------------------------------


def _sha256(path: Path, *, retries: int = 20, delay: float = 0.1) -> str:
    """Read and hash a file's bytes.

    Retries briefly on PermissionError: on Windows, a just-killed
    process's file handle can take a moment to actually release after
    Process.wait() returns, and a read attempted in that window raises
    PermissionError rather than succeeding or raising immediately.
    """
    last_error: PermissionError | None = None
    for _ in range(retries):
        try:
            return hashlib.sha256(path.read_bytes()).hexdigest()
        except PermissionError as exc:
            last_error = exc
            time.sleep(delay)
    assert last_error is not None
    raise last_error


def _deterministic_vector(text: str) -> list[float]:
    seed = int(hashlib.sha256(text.encode()).hexdigest()[:8], 16)
    rng = np.random.default_rng(seed)
    return rng.random(384).tolist()


def _fake_embedder() -> MagicMock:
    embedder = MagicMock()
    embedder.encode.side_effect = lambda batch, **kwargs: np.array(
        [_deterministic_vector(text) for text in batch]
    )
    return embedder


def _seed_conversation(storage: UnifiedStorage, conversation_id: str, *, n_messages: int = 4) -> None:
    now = datetime(2026, 1, 1, 12, 0, 0)
    storage.upsert_conversation(
        conversation_id=conversation_id,
        project_id="proj1",
        file_path=f"/fake/does/not/exist/{conversation_id}.jsonl",
        title=f"Conversation {conversation_id}",
        created_at=now,
        updated_at=now,
        message_count=n_messages,
        full_text="hello world",
        file_hash=f"hash-{conversation_id}",
        indexed_at=now,
    )
    messages = [
        {
            "sequence": i,
            "role": "user" if i % 2 == 0 else "assistant",
            "content": f"{conversation_id} message {i} about sorting a python list",
            "timestamp": now,
            "has_code": False,
            "code_blocks": None,
        }
        for i in range(n_messages)
    ]
    storage.insert_messages(conversation_id, messages)


def _build_indexed_bloated_db(db_path: Path) -> None:
    """A real conversation DB (exchanges/embeddings/FTS/HNSW all populated via
    the same rebuild_derived() path M2 ships) with real reclaimable bloat
    churned in on top, mirroring M1's synthetic-bloat fixture pattern."""
    storage = UnifiedStorage(db_path)
    _seed_conversation(storage, "conv-a")
    _seed_conversation(storage, "conv-b")

    config = Config.load()
    indexer = UnifiedIndexer(db_path.parent, config, storage=storage)
    with patch.object(indexer, "_get_embedder", return_value=_fake_embedder()):
        indexer.rebuild_derived(force=True)
    storage.close()

    # Churn: insert a large padding table and update it across many
    # checkpoints, matching the bloat fixture in
    # tests/unit/services/test_storage_health.py. The table is never
    # dropped: DuckDB's own checkpoint-time truncation only reclaims dead
    # blocks trailing at the file's end, which is exactly what happens if
    # this table were dropped (its blocks, being the newest, sit at the
    # tail and get truncated away for free). Leaving it live scatters the
    # blocks UPDATE orphans throughout the file, interleaved with the real
    # conversation/exchange/embedding data -- the same "used blocks >> live
    # footprint" pattern Appendix A's manual recovery reclaimed, and only a
    # copy-compaction (not a checkpoint) can shrink.
    con = duckdb.connect(str(db_path))
    _prepare_connection(con)
    con.execute("CREATE TABLE _bloat_padding(id INTEGER, payload VARCHAR)")
    con.execute(
        "INSERT INTO _bloat_padding SELECT i, md5(i::VARCHAR) || md5((i + 1)::VARCHAR) || "
        "md5((i + 2)::VARCHAR) FROM range(20000) t(i)"
    )
    con.execute("CHECKPOINT")
    con.close()

    for cycle in range(15):
        con = duckdb.connect(str(db_path))
        _prepare_connection(con)
        con.execute(
            "UPDATE _bloat_padding SET payload = md5((? || id)::VARCHAR) WHERE id % 5 = ?",
            [str(cycle), cycle % 5],
        )
        con.execute("CHECKPOINT")
        con.close()


class TestCompactDatabase:
    """subprocess_isolated=False throughout: these tests exercise the
    compact-verify-swap engine directly. Process isolation itself
    (subprocess_isolated=True, the default) is covered separately."""

    def test_compacts_bloated_fixture_to_query_identical_file(self, tmp_path: Path) -> None:
        db_path = tmp_path / "data" / "searchat.duckdb"
        db_path.parent.mkdir(parents=True)
        _build_indexed_bloated_db(db_path)

        size_before = inspect_database_size(db_path)
        live_before = estimate_live_data_size(db_path)
        ratio_before = compute_bloat_ratio(size_before.total_bytes, live_before)
        assert ratio_before > 1.5  # the churn pattern must have produced measurable bloat

        # Snapshot pre-compaction query results to compare after.
        con = duckdb.connect(str(db_path), read_only=True)
        _prepare_connection(con)
        exchanges_before = con.execute("SELECT * FROM exchanges ORDER BY exchange_id").fetchall()
        bm25_before = con.execute(
            "SELECT exchange_id, fts_main_exchanges.match_bm25(exchange_id, 'sorting') AS score "
            "FROM exchanges WHERE score IS NOT NULL ORDER BY score DESC, exchange_id"
        ).fetchall()
        con.close()

        result = compact_database(db_path, subprocess_isolated=False)

        assert result.success is True
        assert result.error is None
        assert result.preserved_original_path is None
        assert result.verification is not None
        assert result.verification.passed is True
        assert result.bytes_reclaimed > 0
        assert result.compacted_size_bytes < result.original_size_bytes

        # No leftover temp/preserved files.
        leftovers = list(db_path.parent.glob(f"{db_path.name}.*"))
        assert leftovers == []

        con = duckdb.connect(str(db_path), read_only=True)
        _prepare_connection(con)
        exchanges_after = con.execute("SELECT * FROM exchanges ORDER BY exchange_id").fetchall()
        bm25_after = con.execute(
            "SELECT exchange_id, fts_main_exchanges.match_bm25(exchange_id, 'sorting') AS score "
            "FROM exchanges WHERE score IS NOT NULL ORDER BY score DESC, exchange_id"
        ).fetchall()
        hnsw_rows = con.execute(
            "SELECT index_name FROM duckdb_indexes() WHERE index_name = 'verbatim_hnsw'"
        ).fetchall()
        con.close()

        assert exchanges_after == exchanges_before
        assert bm25_after == bm25_before
        assert hnsw_rows == [("verbatim_hnsw",)]

        size_after = inspect_database_size(db_path)
        live_after = estimate_live_data_size(db_path)
        ratio_after = compute_bloat_ratio(size_after.total_bytes, live_after)
        assert ratio_after < ratio_before

    def test_missing_database_returns_clear_failure(self, tmp_path: Path) -> None:
        result = compact_database(tmp_path / "does-not-exist.duckdb", subprocess_isolated=False)

        assert result.success is False
        assert result.original_size_bytes == 0
        assert "No database found" in result.error

    def test_locked_database_refuses_and_leaves_original_untouched(self, tmp_path: Path) -> None:
        """A held write connection must be a genuinely separate OS process --
        DuckDB de-duplicates same-process connections to one file, which
        would mask the cross-process lock this guard exists for."""
        db_path = tmp_path / "data" / "searchat.duckdb"
        db_path.parent.mkdir(parents=True)
        _build_indexed_bloated_db(db_path)
        checksum_before = _sha256(db_path)
        mtime_before = db_path.stat().st_mtime_ns

        holder = subprocess.Popen(
            [
                sys.executable,
                "-c",
                "import duckdb, time, sys; con = duckdb.connect(sys.argv[1]); "
                "print('locked', flush=True); time.sleep(10)",
                str(db_path),
            ],
            stdout=subprocess.PIPE,
            text=True,
        )
        try:
            ready_line = holder.stdout.readline()
            assert ready_line.strip() == "locked"

            result = compact_database(db_path, subprocess_isolated=False)
        finally:
            holder.kill()
            holder.wait(timeout=5)
            holder.stdout.close()

        assert result.success is False
        assert "in use by another process" in result.error
        assert _sha256(db_path) == checksum_before
        assert db_path.stat().st_mtime_ns == mtime_before
        assert not (db_path.parent / f"{db_path.name}.compact-tmp").exists()

    def test_failed_verification_leaves_original_untouched_and_cleans_up_temp(
        self, tmp_path: Path
    ) -> None:
        db_path = tmp_path / "data" / "searchat.duckdb"
        db_path.parent.mkdir(parents=True)
        _build_indexed_bloated_db(db_path)
        checksum_before = _sha256(db_path)

        failing = VerificationResult(
            passed=False,
            row_counts_match=False,
            index_names_match=True,
            fts_probe_match=True,
            vector_probe_match=True,
            symmetric_diff_match=True,
            mismatches=("forced failure for test",),
        )
        with patch("searchat.services.compaction.verify_compaction", return_value=failing):
            result = compact_database(db_path, subprocess_isolated=False)

        assert result.success is False
        assert result.verification is failing
        assert "forced failure for test" in result.error
        assert _sha256(db_path) == checksum_before
        assert not (db_path.parent / f"{db_path.name}.compact-tmp").exists()
        assert list(db_path.parent.glob(f"{db_path.name}.pre-compact-*")) == []

    def test_post_swap_smoke_test_failure_rolls_back_and_quarantines(
        self, tmp_path: Path
    ) -> None:
        """The last line of defense: if the file that just got swapped
        into db_path fails even a trivial open+query smoke test, roll
        back -- restore the original content at db_path, quarantine the
        broken swap-in under a forensic filename, and report failure.
        Nothing is left half-swapped."""
        db_path = tmp_path / "data" / "searchat.duckdb"
        db_path.parent.mkdir(parents=True)
        _build_indexed_bloated_db(db_path)
        checksum_before = _sha256(db_path)

        with patch("searchat.services.compaction._post_swap_smoke_test", return_value=False):
            result = compact_database(db_path, subprocess_isolated=False)

        assert result.success is False
        assert "Post-swap smoke test failed" in result.error
        assert result.preserved_original_path is None
        assert result.quarantined_path is not None
        assert result.quarantined_path.exists()
        assert list(db_path.parent.glob(f"{db_path.name}.post-swap-failed-*")) == [
            result.quarantined_path
        ]

        # The original is back in place at db_path -- verified by content,
        # not just by the field being None.
        assert _sha256(db_path) == checksum_before
        assert list(db_path.parent.glob(f"{db_path.name}.pre-compact-*")) == []

    def test_compacts_database_in_directory_with_apostrophe_in_path(
        self, tmp_path: Path
    ) -> None:
        """ATTACH has no bound-parameter form for its path argument, so
        _sql_literal's manual SQL-literal escaping is what stands between
        a real filesystem path (e.g. a macOS home directory like
        /Users/O'Brien/...) and a broken or injectable ATTACH statement."""
        odd_dir = tmp_path / "O'Brien's Data"
        db_path = odd_dir / "data" / "searchat.duckdb"
        db_path.parent.mkdir(parents=True)
        _build_indexed_bloated_db(db_path)

        result = compact_database(db_path)

        assert result.success is True
        assert result.verification is not None
        assert result.verification.passed is True


class TestSubprocessIsolation:
    """subprocess_isolated=True (the default): compaction runs in a real,
    isolated child process."""

    def test_default_runs_in_subprocess_and_produces_identical_result(
        self, tmp_path: Path
    ) -> None:
        db_path = tmp_path / "data" / "searchat.duckdb"
        db_path.parent.mkdir(parents=True)
        _build_indexed_bloated_db(db_path)

        result = compact_database(db_path)

        assert result.success is True
        assert result.verification is not None
        assert result.verification.passed is True
        assert result.bytes_reclaimed > 0

        con = duckdb.connect(str(db_path), read_only=True)
        _prepare_connection(con)
        row = con.execute("SELECT COUNT(*) FROM exchanges").fetchone()
        con.close()
        assert row == (4,)

    def test_hung_subprocess_is_terminated_after_timeout(self, tmp_path: Path) -> None:
        """A subprocess that neither crashes nor completes within
        timeout_seconds is terminated rather than blocking the caller
        forever -- this branch is what keeps a hung compaction from also
        blocking graceful shutdown (SIGTERM never fires while
        compact_database blocks). Uses a fake process double rather than
        racing a real hang, matching the fault-injection style already
        used for the crash case above."""
        db_path = tmp_path / "data" / "searchat.duckdb"
        db_path.parent.mkdir(parents=True)
        _build_indexed_bloated_db(db_path)
        checksum_before = _sha256(db_path)

        class _HungProcess:
            exitcode = None
            terminate_called = False
            kill_called = False

            def __init__(self, target=None, args=()) -> None:
                del target, args
                self._alive = True

            def start(self) -> None:
                pass

            def join(self, timeout=None) -> None:
                del timeout  # never finishes on its own

            def is_alive(self) -> bool:
                return self._alive

            def terminate(self) -> None:
                type(self).terminate_called = True
                self._alive = False

            def kill(self) -> None:
                type(self).kill_called = True
                self._alive = False

        class _FakeContext:
            def Queue(self):
                return queue.Queue()

            def Process(self, target=None, args=()):
                return _HungProcess(target=target, args=args)

        with patch.object(comp.multiprocessing, "get_context", return_value=_FakeContext()):
            result = compact_database(db_path, timeout_seconds=0.01)

        assert result.success is False
        assert "timed out" in result.error
        assert _HungProcess.terminate_called is True
        assert _HungProcess.kill_called is False
        assert _sha256(db_path) == checksum_before

    def test_kill_subprocess_mid_compaction_leaves_original_untouched(
        self, tmp_path: Path
    ) -> None:
        """The fault-injection case: kill the compaction subprocess right
        after it finishes copying but before it verifies/swaps -- the
        window where a real DuckDB FATAL was observed during Tier 0
        (Appendix A). The original file must be untouched: no swap, no
        preserved-original rename, unchanged checksum and mtime."""
        db_path = tmp_path / "data" / "searchat.duckdb"
        db_path.parent.mkdir(parents=True)
        _build_indexed_bloated_db(db_path)
        checksum_before = _sha256(db_path)
        mtime_before = db_path.stat().st_mtime_ns

        ctx = multiprocessing.get_context("spawn")
        ready_event = ctx.Event()
        result_queue: multiprocessing.Queue = ctx.Queue()
        process = ctx.Process(
            target=comp._compact_worker,
            args=(str(db_path), result_queue, ready_event),
        )
        process.start()
        try:
            signaled = ready_event.wait(timeout=15)
            assert signaled, "worker never reached the pre-verify checkpoint"
            process.kill()
            process.join(timeout=5)
        finally:
            if process.is_alive():
                process.terminate()
                process.join(timeout=5)

        assert process.exitcode != 0
        assert result_queue.empty()
        assert _sha256(db_path) == checksum_before
        assert db_path.stat().st_mtime_ns == mtime_before
        assert list(db_path.parent.glob(f"{db_path.name}.pre-compact-*")) == []

    def test_worker_death_without_result_reported_as_clean_failure(self, tmp_path: Path) -> None:
        """compact_database()'s own orchestration: when its child process
        exits without posting a result to the queue (crash, FATAL abort,
        external kill -- all indistinguishable from here), the failure is
        surfaced as a plain CompactionResult, never an exception, and
        db_path is never touched. Exercised via a fake multiprocessing
        context targeting this branch directly, rather than racing a real
        crash (already covered by the kill test above, which proves the
        file-safety property against a genuine subprocess)."""
        db_path = tmp_path / "data" / "searchat.duckdb"
        db_path.parent.mkdir(parents=True)
        _build_indexed_bloated_db(db_path)
        checksum_before = _sha256(db_path)

        class _DeadProcess:
            exitcode = -9

            def __init__(self, target=None, args=()) -> None:
                del target, args

            def start(self) -> None:
                pass

            def join(self, timeout=None) -> None:
                del timeout

            def is_alive(self) -> bool:
                return False

        class _FakeContext:
            def Queue(self):
                return queue.Queue()  # always empty: the "worker" never posted

            def Process(self, target=None, args=()):
                return _DeadProcess(target=target, args=args)

        with patch.object(comp.multiprocessing, "get_context", return_value=_FakeContext()):
            result = compact_database(db_path)

        assert result.success is False
        assert "subprocess exited abnormally" in result.error
        assert "-9" in result.error
        assert _sha256(db_path) == checksum_before


# ---------------------------------------------------------------------------
# Auto-trigger: should_auto_compact (pure), compaction-state sidecar, and
# run_auto_compact_if_needed (integration)
# ---------------------------------------------------------------------------


class TestShouldAutoCompact:
    def test_ratio_at_or_below_threshold_never_fires(self) -> None:
        assert comp.should_auto_compact(
            bloat_ratio=3.0, last_compaction_at=None, auto_trigger_ratio=3.0, min_interval_days=7
        ) is False
        assert comp.should_auto_compact(
            bloat_ratio=2.9, last_compaction_at=None, auto_trigger_ratio=3.0, min_interval_days=7
        ) is False

    def test_ratio_above_threshold_fires_when_never_compacted(self) -> None:
        assert comp.should_auto_compact(
            bloat_ratio=3.1, last_compaction_at=None, auto_trigger_ratio=3.0, min_interval_days=7
        ) is True

    def test_ratio_above_threshold_blocked_by_recent_compaction(self) -> None:
        now = datetime(2026, 7, 2, tzinfo=timezone.utc)
        recent = now - timedelta(days=1)
        assert comp.should_auto_compact(
            bloat_ratio=10.0,
            last_compaction_at=recent,
            auto_trigger_ratio=3.0,
            min_interval_days=7,
            now=now,
        ) is False

    def test_ratio_above_threshold_fires_after_interval_elapses(self) -> None:
        now = datetime(2026, 7, 2, tzinfo=timezone.utc)
        old = now - timedelta(days=8)
        assert comp.should_auto_compact(
            bloat_ratio=10.0,
            last_compaction_at=old,
            auto_trigger_ratio=3.0,
            min_interval_days=7,
            now=now,
        ) is True

    def test_exact_interval_boundary_fires(self) -> None:
        now = datetime(2026, 7, 2, tzinfo=timezone.utc)
        exactly_seven_days_ago = now - timedelta(days=7)
        assert comp.should_auto_compact(
            bloat_ratio=10.0,
            last_compaction_at=exactly_seven_days_ago,
            auto_trigger_ratio=3.0,
            min_interval_days=7,
            now=now,
        ) is True


class TestCompactionState:
    def test_missing_state_returns_none(self, tmp_path: Path) -> None:
        state = comp.read_compaction_state(tmp_path)
        assert state.last_compaction_at is None

    def test_record_then_read_round_trips(self, tmp_path: Path) -> None:
        at = datetime(2026, 7, 1, 12, 0, 0, tzinfo=timezone.utc)
        comp.record_compaction_completed(tmp_path, at=at)

        state = comp.read_compaction_state(tmp_path)

        assert state.last_compaction_at == at

    def test_malformed_state_file_degrades_to_none(self, tmp_path: Path) -> None:
        path = tmp_path / "data" / "compaction_state.json"
        path.parent.mkdir(parents=True)
        path.write_text("not json")

        state = comp.read_compaction_state(tmp_path)

        assert state.last_compaction_at is None


class TestRunAutoCompactIfNeeded:
    """Bloat ratio is controlled by patching compute_bloat_ratio's return
    value rather than depending on a fixture's exact (variable) real
    bloat, so ratio-threshold behavior is tested deterministically while
    inspect_database_size/estimate_live_data_size still run for real
    against a real fixture, exercising the actual integration wiring."""

    def test_missing_database_returns_none(self, tmp_path: Path) -> None:
        result = comp.run_auto_compact_if_needed(
            tmp_path / "missing.duckdb", tmp_path, auto_trigger_ratio=3.0, min_interval_days=7
        )
        assert result is None

    def test_fires_and_records_state_above_threshold_never_compacted(self, tmp_path: Path) -> None:
        search_dir = tmp_path
        db_path = search_dir / "data" / "searchat.duckdb"
        db_path.parent.mkdir(parents=True)
        _build_indexed_bloated_db(db_path)

        with patch("searchat.services.storage_health.compute_bloat_ratio", return_value=3.5):
            result = comp.run_auto_compact_if_needed(
                db_path, search_dir, auto_trigger_ratio=3.0, min_interval_days=7
            )

        assert result is not None
        assert result.success is True
        state = comp.read_compaction_state(search_dir)
        assert state.last_compaction_at is not None

    def test_does_not_fire_at_or_below_threshold(self, tmp_path: Path) -> None:
        search_dir = tmp_path
        db_path = search_dir / "data" / "searchat.duckdb"
        db_path.parent.mkdir(parents=True)
        _build_indexed_bloated_db(db_path)
        checksum_before = _sha256(db_path)

        for ratio in (3.0, 2.5):
            with patch("searchat.services.storage_health.compute_bloat_ratio", return_value=ratio):
                result = comp.run_auto_compact_if_needed(
                    db_path, search_dir, auto_trigger_ratio=3.0, min_interval_days=7
                )
            assert result is None, f"must not fire at ratio={ratio}"

        assert _sha256(db_path) == checksum_before
        assert comp.read_compaction_state(search_dir).last_compaction_at is None

    def test_does_not_fire_when_recently_compacted_even_if_bloated(self, tmp_path: Path) -> None:
        search_dir = tmp_path
        db_path = search_dir / "data" / "searchat.duckdb"
        db_path.parent.mkdir(parents=True)
        _build_indexed_bloated_db(db_path)
        comp.record_compaction_completed(search_dir, at=datetime.now(timezone.utc))
        checksum_before = _sha256(db_path)

        with patch("searchat.services.storage_health.compute_bloat_ratio", return_value=10.0):
            result = comp.run_auto_compact_if_needed(
                db_path, search_dir, auto_trigger_ratio=3.0, min_interval_days=7
            )

        assert result is None
        assert _sha256(db_path) == checksum_before

    def test_reuses_live_connection_without_opening_a_conflicting_one(self, tmp_path: Path) -> None:
        """Regression test: `api/dependencies.py::maybe_auto_compact_on_shutdown`
        passes the live server's own (`read_only=False`) `UnifiedStorage`
        connection as `conn`. Before this fix, the bloat-ratio size checks
        below always opened a second, differently-configured connection to
        the same file, which DuckDB rejects from within the same process --
        silently disabling the shutdown auto-trigger on every real deployment.
        """
        search_dir = tmp_path
        db_path = search_dir / "data" / "searchat.duckdb"
        db_path.parent.mkdir(parents=True)
        _build_indexed_bloated_db(db_path)

        live_conn = duckdb.connect(str(db_path), read_only=False)
        try:
            with patch("searchat.services.storage_health.compute_bloat_ratio", return_value=2.5):
                result = comp.run_auto_compact_if_needed(
                    db_path, search_dir, auto_trigger_ratio=3.0, min_interval_days=7, conn=live_conn
                )
        finally:
            live_conn.close()

        # Below threshold: never fires. The point of this test is that the
        # in-process size checks above did not raise while `live_conn` was open.
        assert result is None

    def test_never_raises_on_internal_error(self, tmp_path: Path) -> None:
        search_dir = tmp_path
        db_path = search_dir / "data" / "searchat.duckdb"
        db_path.parent.mkdir(parents=True)
        _build_indexed_bloated_db(db_path)

        with patch(
            "searchat.services.storage_health.inspect_database_size",
            side_effect=RuntimeError("boom"),
        ):
            result = comp.run_auto_compact_if_needed(
                db_path, search_dir, auto_trigger_ratio=3.0, min_interval_days=7
            )

        assert result is None
