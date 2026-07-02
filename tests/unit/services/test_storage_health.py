from __future__ import annotations

import json
import shutil
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import Mock

import duckdb
import pytest

from searchat.services.backup import BackupManager
from searchat.services.storage_contracts import BACKUP_MANIFEST_FILE
from searchat.services.storage_health import (
    HarnessSourceSize,
    audit_backup_redundancy,
    build_storage_doctor_report,
    compute_bloat_ratio,
    estimate_harness_source_sizes,
    estimate_last_backup_age,
    estimate_live_data_size,
    inspect_database_size,
    inspect_storage_health,
    repair_storage_metadata,
)


def test_inspect_storage_health_flags_repairable_legacy_backup_metadata(temp_search_dir: Path) -> None:
    manager = BackupManager(temp_search_dir)
    live_file = temp_search_dir / "data" / "conversations" / "conv.parquet"
    live_file.parent.mkdir(parents=True, exist_ok=True)
    live_file.write_bytes(b"PAR1\n")

    backup = manager.create_backup(backup_name="legacy")
    metadata_path = backup.backup_path / manager.METADATA_FILE
    payload = json.loads(metadata_path.read_text(encoding="utf-8"))
    payload.pop("metadata_version", None)
    metadata_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    report = inspect_storage_health(temp_search_dir)

    assert any(issue.scope == "backup_metadata" and issue.repairable for issue in report.issues)


def test_repair_storage_metadata_normalizes_legacy_backup_metadata(temp_search_dir: Path) -> None:
    manager = BackupManager(temp_search_dir)
    live_file = temp_search_dir / "data" / "conversations" / "conv.parquet"
    live_file.parent.mkdir(parents=True, exist_ok=True)
    live_file.write_bytes(b"PAR1\n")

    backup = manager.create_backup(backup_name="legacy")
    metadata_path = backup.backup_path / manager.METADATA_FILE
    payload = json.loads(metadata_path.read_text(encoding="utf-8"))
    payload.pop("metadata_version", None)
    metadata_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    report = repair_storage_metadata(temp_search_dir)

    assert report.repairs_applied == 1
    repaired_payload = json.loads(metadata_path.read_text(encoding="utf-8"))
    assert repaired_payload["metadata_version"] == 1


def test_repair_storage_metadata_normalizes_legacy_backup_manifest_fixture(temp_search_dir: Path) -> None:
    fixture = Path("tests/fixtures/storage/backup_contract_bundle")
    shutil.copytree(fixture, temp_search_dir, dirs_exist_ok=True)

    report = repair_storage_metadata(temp_search_dir)

    assert report.repairs_applied >= 1
    manifest_payload = json.loads(
        (
            temp_search_dir
            / "backups"
            / "repairable_manifest_base"
            / "backup_manifest.json"
        ).read_text(encoding="utf-8")
    )
    assert manifest_payload["manifest_version"] == 1


def test_inspect_storage_health_flags_legacy_backup_dataset_index_metadata(temp_search_dir: Path) -> None:
    fixture = Path("tests/fixtures/storage/legacy_dataset_bundle")
    shutil.copytree(fixture, temp_search_dir, dirs_exist_ok=True)

    report = inspect_storage_health(temp_search_dir, embedding_model="all-MiniLM-L6-v2")

    assert any(issue.scope == "backup_index_metadata" and issue.repairable for issue in report.issues)


def test_repair_storage_metadata_migrates_legacy_dataset_bundle(temp_search_dir: Path) -> None:
    fixture = Path("tests/fixtures/storage/legacy_dataset_bundle")
    shutil.copytree(fixture, temp_search_dir, dirs_exist_ok=True)

    report = repair_storage_metadata(temp_search_dir, embedding_model="all-MiniLM-L6-v2")

    assert report.repairs_applied == 3

    live_payload = json.loads(
        (temp_search_dir / "data" / "indices" / "index_metadata.json").read_text(encoding="utf-8")
    )
    backup_payload = json.loads(
        (
            temp_search_dir
            / "backups"
            / "legacy_full_dataset"
            / "data"
            / "indices"
            / "index_metadata.json"
        ).read_text(encoding="utf-8")
    )
    backup_meta = json.loads(
        (temp_search_dir / "backups" / "legacy_full_dataset" / "backup_metadata.json").read_text(encoding="utf-8")
    )

    assert live_payload["embedding_model"] == "all-MiniLM-L6-v2"
    assert live_payload["next_vector_id"] == 3
    assert backup_payload["embedding_model"] == "all-MiniLM-L6-v2"
    assert backup_payload["next_vector_id"] == 4
    assert backup_meta["metadata_version"] == 1


def test_inspect_storage_health_flags_broken_backup_chain(temp_search_dir: Path) -> None:
    manager = BackupManager(temp_search_dir)
    live_file = temp_search_dir / "data" / "conversations" / "conv.parquet"
    settings = temp_search_dir / "config" / "settings.toml"
    live_file.parent.mkdir(parents=True, exist_ok=True)
    settings.parent.mkdir(parents=True, exist_ok=True)
    live_file.write_bytes(b"PAR1\n")
    settings.write_bytes(b"a = 1\n")

    base = manager.create_backup(backup_name="base")
    settings.write_bytes(b"a = 2\n")
    child = manager.create_incremental_backup(parent_name=base.backup_path.name, backup_name="child")
    (base.backup_path / BACKUP_MANIFEST_FILE).unlink()

    report = inspect_storage_health(temp_search_dir)

    assert any(
        issue.scope == "backup_chain"
        and child.backup_path.name in issue.message
        and issue.severity == "error"
        for issue in report.issues
    )


def test_inspect_storage_health_flags_fixture_backup_contract_bundle(temp_search_dir: Path) -> None:
    fixture = Path("tests/fixtures/storage/backup_contract_bundle")
    shutil.copytree(fixture, temp_search_dir, dirs_exist_ok=True)

    report = inspect_storage_health(temp_search_dir)

    assert any(
        issue.scope == "backup_manifest"
        and issue.path.name == BACKUP_MANIFEST_FILE
        and "version mismatch" in issue.message.lower()
        for issue in report.issues
    )
    assert any(
        issue.scope == "backup_chain"
        and issue.path.name == "broken_chain_child"
        and "validation failed" in issue.message.lower()
        for issue in report.issues
    )
    assert any(
        issue.scope == "backup_metadata"
        and issue.path.parent.name == "mixed_version_metadata_full"
        and "version mismatch" in issue.message.lower()
        for issue in report.issues
    )
    assert any(
        issue.scope == "backup_manifest"
        and issue.path.parent.name == "repairable_manifest_base"
        and issue.repairable
        for issue in report.issues
    )


# ---------------------------------------------------------------------------
# Storage doctor diagnostics: live-data size estimation
# ---------------------------------------------------------------------------


def test_inspect_database_size_missing_file_returns_zeros(tmp_path: Path) -> None:
    info = inspect_database_size(tmp_path / "missing.duckdb")
    assert info.total_bytes == 0
    assert info.block_size == 0
    assert info.wal_bytes == 0


def test_estimate_live_data_size_missing_file_returns_zero(tmp_path: Path) -> None:
    assert estimate_live_data_size(tmp_path / "missing.duckdb") == 0


def test_estimate_live_data_size_matches_known_block_count(tmp_path: Path) -> None:
    db_path = tmp_path / "live.duckdb"
    con = duckdb.connect(str(db_path))
    con.execute("CREATE TABLE conversations(id INTEGER, payload VARCHAR)")
    con.execute(
        "INSERT INTO conversations SELECT i, md5(i::VARCHAR) || md5((i + 1)::VARCHAR) "
        "FROM range(5000) t(i)"
    )
    con.execute("CHECKPOINT")

    known_blocks = {
        int(row[0])
        for row in con.execute(
            "SELECT DISTINCT block_id FROM pragma_storage_info('\"main\".\"conversations\"') "
            "WHERE block_id IS NOT NULL AND block_id >= 0"
        ).fetchall()
    }
    block_size = int(
        con.execute("PRAGMA database_size").fetchdf()["block_size"][0]
    )
    con.close()

    assert estimate_live_data_size(db_path) == len(known_blocks) * block_size


def test_compute_bloat_ratio_pure_math() -> None:
    assert compute_bloat_ratio(3_000_000, 1_000_000) == pytest.approx(3.0)
    assert compute_bloat_ratio(1_000_000, 1_000_000) == pytest.approx(1.0)


def test_compute_bloat_ratio_degenerate_inputs_return_one() -> None:
    assert compute_bloat_ratio(0, 0) == 1.0
    assert compute_bloat_ratio(100, 0) == 1.0
    assert compute_bloat_ratio(0, 100) == 1.0


def _duckdb_size_info(con: duckdb.DuckDBPyConnection) -> tuple[int, int]:
    cursor = con.execute("PRAGMA database_size")
    row = cursor.fetchone()
    assert row is not None
    columns = {desc[0]: value for desc, value in zip(cursor.description, row)}
    return int(columns["block_size"]), int(columns["total_blocks"])


def _live_blocks(con: duckdb.DuckDBPyConnection, schema: str, table: str) -> set[int]:
    qualified = f'"{schema}"."{table}"'
    rows = con.execute(
        "SELECT DISTINCT block_id FROM pragma_storage_info(?) WHERE block_id IS NOT NULL AND block_id >= 0",
        [qualified],
    ).fetchall()
    return {int(row[0]) for row in rows}


def _build_bloated_fixture_db(db_path: Path) -> None:
    """Insert incompressible data, then churn it with deterministic updates across many
    separate connections and checkpoints, so DuckDB's block allocator leaves free blocks
    behind: the "used blocks >> live table footprint" pattern this module flags as bloat.
    """
    con = duckdb.connect(str(db_path))
    con.execute("CREATE TABLE live_data(id INTEGER, payload VARCHAR)")
    con.execute(
        "INSERT INTO live_data SELECT i, md5(i::VARCHAR) || md5((i + 1)::VARCHAR) || md5((i + 2)::VARCHAR) "
        "FROM range(20000) t(i)"
    )
    con.execute("CHECKPOINT")
    con.close()

    for cycle in range(15):
        con = duckdb.connect(str(db_path))
        con.execute(
            "UPDATE live_data SET payload = md5((? || id)::VARCHAR) || md5((? || id + 1)::VARCHAR) "
            "WHERE id % 5 = ?",
            [str(cycle), str(cycle), cycle % 5],
        )
        con.execute("CHECKPOINT")
        con.close()


def test_estimate_live_data_size_and_bloat_ratio_detect_synthetic_bloat(tmp_path: Path) -> None:
    db_path = tmp_path / "bloat.duckdb"
    _build_bloated_fixture_db(db_path)

    # Independently recompute the fixture's known ratio straight from DuckDB's own
    # pragmas, without going through the functions under test.
    con = duckdb.connect(str(db_path), read_only=True)
    block_size, total_blocks = _duckdb_size_info(con)
    known_live_blocks = _live_blocks(con, "main", "live_data")
    con.close()

    known_total_bytes = block_size * total_blocks
    known_live_bytes = len(known_live_blocks) * block_size
    known_ratio = known_total_bytes / known_live_bytes

    size_info = inspect_database_size(db_path)
    live_bytes = estimate_live_data_size(db_path)
    ratio = compute_bloat_ratio(size_info.total_bytes, live_bytes)

    assert size_info.total_bytes == known_total_bytes
    assert live_bytes == known_live_bytes
    assert ratio == pytest.approx(known_ratio, rel=0.05)
    # The churn pattern must actually have produced measurable bloat for this fixture
    # to be meaningful (used blocks left behind beyond the live table's footprint).
    assert ratio > 1.0


# ---------------------------------------------------------------------------
# Storage doctor diagnostics: backup redundancy audit
# ---------------------------------------------------------------------------


def test_audit_backup_redundancy_flags_strict_subset_as_redundant(temp_search_dir: Path) -> None:
    data_root = temp_search_dir / "data" / "conversations"
    data_root.mkdir(parents=True, exist_ok=True)
    (data_root / "conv1.parquet").write_bytes(b"PAR1conv1data")
    (data_root / "conv2.parquet").write_bytes(b"PAR1conv2data")

    manager = BackupManager(temp_search_dir)
    manager.create_backup(backup_name="snap1")

    # Live data grows after the backup — the backup's files remain a strict subset.
    (data_root / "conv3.parquet").write_bytes(b"PAR1conv3newdata")

    audits = audit_backup_redundancy(temp_search_dir / "backups", temp_search_dir)

    assert len(audits) == 1
    assert audits[0].file_count == 2
    assert audits[0].redundant is True
    assert audits[0].unique_files == ()


def test_audit_backup_redundancy_flags_modified_live_file_as_not_redundant(temp_search_dir: Path) -> None:
    data_root = temp_search_dir / "data" / "conversations"
    data_root.mkdir(parents=True, exist_ok=True)
    (data_root / "conv1.parquet").write_bytes(b"PAR1conv1data")

    manager = BackupManager(temp_search_dir)
    manager.create_backup(backup_name="snap1")

    (data_root / "conv1.parquet").write_bytes(b"MODIFIED-CONTENT")

    audits = audit_backup_redundancy(temp_search_dir / "backups", temp_search_dir)

    assert len(audits) == 1
    assert audits[0].redundant is False
    assert audits[0].unique_files == ("data/conversations/conv1.parquet",)


def test_audit_backup_redundancy_missing_backup_dir_returns_empty(tmp_path: Path) -> None:
    assert audit_backup_redundancy(tmp_path / "no_backups", tmp_path) == []


# ---------------------------------------------------------------------------
# Storage doctor diagnostics: harness sizes, backup age, and full report
# ---------------------------------------------------------------------------


def test_estimate_harness_source_sizes_sums_discovered_files(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    file_a = tmp_path / "a.jsonl"
    file_a.write_bytes(b"x" * 100)
    file_b = tmp_path / "b.jsonl"
    file_b.write_bytes(b"y" * 250)

    fake_connector = Mock()
    fake_connector.name = "fake_harness"
    fake_connector.discover_files.return_value = [file_a, file_b]

    monkeypatch.setattr(
        "searchat.services.storage_health.get_connectors", lambda: (fake_connector,)
    )

    sizes = estimate_harness_source_sizes(Mock())

    assert sizes == [HarnessSourceSize(connector="fake_harness", file_count=2, total_size_bytes=350)]


def test_estimate_harness_source_sizes_skips_failing_connector(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    broken_connector = Mock()
    broken_connector.name = "broken"
    broken_connector.discover_files.side_effect = RuntimeError("harness unavailable")

    monkeypatch.setattr(
        "searchat.services.storage_health.get_connectors", lambda: (broken_connector,)
    )

    assert estimate_harness_source_sizes(Mock()) == []


def test_estimate_last_backup_age_returns_none_when_no_backups(temp_search_dir: Path) -> None:
    assert estimate_last_backup_age(temp_search_dir) == (None, None)


def test_estimate_last_backup_age_computes_seconds_since_latest(temp_search_dir: Path) -> None:
    manager = BackupManager(temp_search_dir)
    live_file = temp_search_dir / "data" / "conversations" / "conv.parquet"
    live_file.parent.mkdir(parents=True, exist_ok=True)
    live_file.write_bytes(b"PAR1")
    manager.create_backup(backup_name="snap1")

    backed_at = datetime.strptime(manager.list_backups()[0].timestamp, "%Y%m%d_%H%M%S")

    last_at, age_seconds = estimate_last_backup_age(temp_search_dir, now=backed_at + timedelta(hours=2))

    assert last_at == backed_at.isoformat()
    assert age_seconds == pytest.approx(7200, abs=1)


def test_build_storage_doctor_report_assembles_all_sections(
    temp_search_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    data_root = temp_search_dir / "data"
    (data_root / "conversations").mkdir(parents=True, exist_ok=True)
    (data_root / "conversations" / "conv.parquet").write_bytes(b"PAR1conv")

    db_path = data_root / "searchat.duckdb"
    con = duckdb.connect(str(db_path))
    con.execute("CREATE TABLE conversations(id INTEGER)")
    con.execute("INSERT INTO conversations SELECT * FROM range(10)")
    con.execute("CHECKPOINT")
    con.close()

    manager = BackupManager(temp_search_dir)
    manager.create_backup(backup_name="snap1")

    monkeypatch.setattr("searchat.services.storage_health.get_connectors", lambda: ())

    config = Mock()
    config.storage.resolve_duckdb_path.return_value = db_path

    report = build_storage_doctor_report(temp_search_dir, config)

    assert report.db_path == db_path
    assert report.db_exists is True
    assert report.total_bytes > 0
    assert report.live_bytes > 0
    assert report.bloat_ratio >= 1.0
    assert len(report.backups) == 1
    assert report.backups[0].redundant is True
    assert report.harness_sources == ()
    assert report.last_backup_at is not None
    assert report.last_backup_age_seconds is not None
    assert report.last_backup_age_seconds >= 0

    payload = report.to_dict()
    assert payload["db_exists"] is True
    assert isinstance(payload["backups"], list)
    assert isinstance(payload["harness_sources"], list)
