"""Unit tests for services/compaction.py -- verified copy-compaction engine."""
from __future__ import annotations

import hashlib
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock, patch

import duckdb
import numpy as np

from searchat.config import Config
from searchat.core.unified_indexer import UnifiedIndexer
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


# ---------------------------------------------------------------------------
# Real, indexed conversation DB with synthetic bloat -- end-to-end engine tests
# ---------------------------------------------------------------------------


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


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

        result = compact_database(db_path)

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
        result = compact_database(tmp_path / "does-not-exist.duckdb")

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

            result = compact_database(db_path)
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
            result = compact_database(db_path)

        assert result.success is False
        assert result.verification is failing
        assert "forced failure for test" in result.error
        assert _sha256(db_path) == checksum_before
        assert not (db_path.parent / f"{db_path.name}.compact-tmp").exists()
        assert list(db_path.parent.glob(f"{db_path.name}.pre-compact-*")) == []
