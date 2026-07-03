"""Unit tests for `searchat doctor` CLI command."""
from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import duckdb
import pytest

from searchat.services.backup import BackupManager


def _cfg(search_dir: Path) -> SimpleNamespace:
    """Minimal Config stand-in exposing only what run_doctor touches."""
    return SimpleNamespace(
        storage=SimpleNamespace(resolve_duckdb_path=lambda _search_dir: search_dir / "data" / "searchat.duckdb")
    )


def test_doctor_help_text(capsys) -> None:
    from searchat.cli.doctor_cmd import run_doctor

    with pytest.raises(SystemExit) as exc_info:
        run_doctor(["--help"])
    assert exc_info.value.code == 0

    captured = capsys.readouterr()
    assert "doctor" in captured.out.lower()
    assert "--json" in captured.out


def test_doctor_reports_friendly_message_when_no_db_exists(temp_search_dir: Path, capsys) -> None:
    from searchat.cli.doctor_cmd import run_doctor

    with (
        patch("searchat.config.Config.load", return_value=_cfg(temp_search_dir)),
        patch("searchat.config.PathResolver.get_shared_search_dir", return_value=temp_search_dir),
        patch("searchat.services.storage_health.get_connectors", return_value=()),
    ):
        result = run_doctor([])

    captured = capsys.readouterr()
    assert result == 0
    assert "no duckdb index found" in captured.out.lower()


def test_doctor_table_output_shows_bloat_ratio_and_backups(temp_search_dir: Path, capsys) -> None:
    from searchat.cli.doctor_cmd import run_doctor

    data_dir = temp_search_dir / "data"
    data_dir.mkdir(parents=True, exist_ok=True)
    db_path = data_dir / "searchat.duckdb"
    con = duckdb.connect(str(db_path))
    con.execute("CREATE TABLE dummy_bloat(id INTEGER)")
    con.execute("INSERT INTO dummy_bloat SELECT * FROM range(5)")
    con.execute("CHECKPOINT")
    con.close()

    manager = BackupManager(temp_search_dir)
    (data_dir / "conversations" / "conv.parquet").parent.mkdir(parents=True, exist_ok=True)
    (data_dir / "conversations" / "conv.parquet").write_bytes(b"PAR1")
    manager.create_backup(backup_name="snap1")

    with (
        patch("searchat.config.Config.load", return_value=_cfg(temp_search_dir)),
        patch("searchat.config.PathResolver.get_shared_search_dir", return_value=temp_search_dir),
        patch("searchat.services.storage_health.get_connectors", return_value=()),
    ):
        result = run_doctor([])

    captured = capsys.readouterr()
    assert result == 0
    assert "Bloat ratio" in captured.out
    assert "Backups" in captured.out
    assert "snap1" in captured.out
    assert "Redundant" in captured.out


def test_doctor_json_output_matches_documented_schema(temp_search_dir: Path, capsys) -> None:
    from searchat.cli.doctor_cmd import run_doctor

    data_dir = temp_search_dir / "data"
    data_dir.mkdir(parents=True, exist_ok=True)
    db_path = data_dir / "searchat.duckdb"
    con = duckdb.connect(str(db_path))
    con.execute("CREATE TABLE dummy_bloat(id INTEGER)")
    con.execute("INSERT INTO dummy_bloat SELECT * FROM range(5)")
    con.execute("CHECKPOINT")
    con.close()

    manager = BackupManager(temp_search_dir)
    (data_dir / "conversations").mkdir(parents=True, exist_ok=True)
    (data_dir / "conversations" / "conv.parquet").write_bytes(b"PAR1")
    manager.create_backup(backup_name="snap1")

    with (
        patch("searchat.config.Config.load", return_value=_cfg(temp_search_dir)),
        patch("searchat.config.PathResolver.get_shared_search_dir", return_value=temp_search_dir),
        patch("searchat.services.storage_health.get_connectors", return_value=()),
    ):
        result = run_doctor(["--json"])

    captured = capsys.readouterr()
    assert result == 0
    payload = json.loads(captured.out)

    # Top-level schema.
    assert set(payload.keys()) == {
        "search_dir",
        "db_path",
        "db_exists",
        "total_bytes",
        "live_bytes",
        "wal_bytes",
        "bloat_ratio",
        "backups",
        "harness_sources",
        "last_backup_at",
        "last_backup_age_seconds",
    }
    assert isinstance(payload["db_exists"], bool)
    assert isinstance(payload["total_bytes"], int)
    assert isinstance(payload["live_bytes"], int)
    assert isinstance(payload["wal_bytes"], int)
    assert isinstance(payload["bloat_ratio"], (int, float))
    assert isinstance(payload["backups"], list)
    assert isinstance(payload["harness_sources"], list)

    assert len(payload["backups"]) == 1
    backup_entry = payload["backups"][0]
    assert set(backup_entry.keys()) == {
        "backup_name",
        "backup_path",
        "file_count",
        "total_size_bytes",
        "redundant",
        "unique_files",
    }
    assert isinstance(backup_entry["redundant"], bool)
    assert isinstance(backup_entry["unique_files"], list)
    assert backup_entry["redundant"] is True


def test_doctor_json_reports_synthetic_bloat_ratio(temp_search_dir: Path, capsys) -> None:
    """CLI-level acceptance check: a fixture DB with deliberate bloat reports a
    ratio consistent with an independently-derived reference (>1.0, and within
    5% of the same raw-pragma computation used in the engine-level test)."""
    from searchat.cli.doctor_cmd import run_doctor

    data_dir = temp_search_dir / "data"
    data_dir.mkdir(parents=True, exist_ok=True)
    db_path = data_dir / "searchat.duckdb"

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

    con = duckdb.connect(str(db_path), read_only=True)
    size_row = con.execute("PRAGMA database_size").fetchone()
    columns = {desc[0]: value for desc, value in zip(con.description, size_row)}
    block_size, total_blocks = int(columns["block_size"]), int(columns["total_blocks"])
    known_live_blocks = {
        int(row[0])
        for row in con.execute(
            "SELECT DISTINCT block_id FROM pragma_storage_info('\"main\".\"live_data\"') "
            "WHERE block_id IS NOT NULL AND block_id >= 0"
        ).fetchall()
    }
    con.close()
    known_ratio = (total_blocks * block_size) / (len(known_live_blocks) * block_size)

    with (
        patch("searchat.config.Config.load", return_value=_cfg(temp_search_dir)),
        patch("searchat.config.PathResolver.get_shared_search_dir", return_value=temp_search_dir),
        patch("searchat.services.storage_health.get_connectors", return_value=()),
    ):
        result = run_doctor(["--json"])

    captured = capsys.readouterr()
    assert result == 0
    payload = json.loads(captured.out)

    assert payload["bloat_ratio"] > 1.0
    assert payload["bloat_ratio"] == pytest.approx(known_ratio, rel=0.05)


def test_doctor_returns_one_and_prints_error_on_failure(temp_search_dir: Path, capsys) -> None:
    from searchat.cli.doctor_cmd import run_doctor

    with (
        patch("searchat.config.Config.load", return_value=_cfg(temp_search_dir)),
        patch("searchat.config.PathResolver.get_shared_search_dir", return_value=temp_search_dir),
        patch(
            "searchat.services.storage_health.build_storage_doctor_report",
            side_effect=RuntimeError("disk read failed"),
        ),
    ):
        result = run_doctor([])

    captured = capsys.readouterr()
    assert result == 1
    assert "disk read failed" in captured.err
