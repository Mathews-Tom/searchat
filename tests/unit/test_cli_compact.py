"""Unit tests for `searchat compact` CLI command."""
from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from searchat.services.compaction import CompactionResult, VerificationResult


def _cfg(search_dir: Path) -> SimpleNamespace:
    """Minimal Config stand-in exposing only what run_compact touches."""
    return SimpleNamespace(
        storage=SimpleNamespace(resolve_duckdb_path=lambda _search_dir: search_dir / "data" / "searchat.duckdb")
    )


def _success_result(db_path: Path) -> CompactionResult:
    return CompactionResult(
        success=True,
        original_path=db_path,
        original_size_bytes=6_000_000,
        compacted_size_bytes=1_500_000,
        bytes_reclaimed=4_500_000,
        preserved_original_path=None,
        verification=VerificationResult(
            passed=True,
            row_counts_match=True,
            index_names_match=True,
            fts_probe_match=True,
            vector_probe_match=True,
            symmetric_diff_match=True,
            mismatches=(),
        ),
        error=None,
        duration_seconds=1.23,
    )


def _failure_result(db_path: Path) -> CompactionResult:
    return CompactionResult(
        success=False,
        original_path=db_path,
        original_size_bytes=6_000_000,
        compacted_size_bytes=0,
        bytes_reclaimed=0,
        preserved_original_path=None,
        verification=None,
        error="Database is in use by another process; refusing to compact",
        duration_seconds=0.05,
    )


def test_compact_help_text(capsys) -> None:
    from searchat.cli.compact_cmd import run_compact

    with pytest.raises(SystemExit) as exc_info:
        run_compact(["--help"])
    assert exc_info.value.code == 0

    captured = capsys.readouterr()
    assert "compact" in captured.out.lower()
    assert "--json" in captured.out
    assert "--in-process" in captured.out


def test_compact_success_summary_output(temp_search_dir: Path, capsys) -> None:
    from searchat.cli.compact_cmd import run_compact

    db_path = temp_search_dir / "data" / "searchat.duckdb"
    with (
        patch("searchat.config.Config.load", return_value=_cfg(temp_search_dir)),
        patch("searchat.config.PathResolver.get_shared_search_dir", return_value=temp_search_dir),
        patch(
            "searchat.services.compaction.compact_database", return_value=_success_result(db_path)
        ) as mock_compact,
        patch("searchat.services.compaction.record_compaction_completed") as mock_record,
    ):
        result = run_compact([])

    captured = capsys.readouterr()
    assert result == 0
    assert "Compaction complete" in captured.out
    assert "Bytes reclaimed" in captured.out
    mock_compact.assert_called_once_with(db_path, subprocess_isolated=True)
    mock_record.assert_called_once_with(temp_search_dir)


def test_compact_success_json_output(temp_search_dir: Path, capsys) -> None:
    from searchat.cli.compact_cmd import run_compact

    db_path = temp_search_dir / "data" / "searchat.duckdb"
    with (
        patch("searchat.config.Config.load", return_value=_cfg(temp_search_dir)),
        patch("searchat.config.PathResolver.get_shared_search_dir", return_value=temp_search_dir),
        patch("searchat.services.compaction.compact_database", return_value=_success_result(db_path)),
        patch("searchat.services.compaction.record_compaction_completed"),
    ):
        result = run_compact(["--json"])

    captured = capsys.readouterr()
    assert result == 0
    payload = json.loads(captured.out)
    assert payload["success"] is True
    assert payload["bytes_reclaimed"] == 4_500_000
    assert payload["verification"]["passed"] is True
    assert payload["error"] is None


def test_compact_failure_summary_output_does_not_record_state(
    temp_search_dir: Path, capsys
) -> None:
    from searchat.cli.compact_cmd import run_compact

    db_path = temp_search_dir / "data" / "searchat.duckdb"
    with (
        patch("searchat.config.Config.load", return_value=_cfg(temp_search_dir)),
        patch("searchat.config.PathResolver.get_shared_search_dir", return_value=temp_search_dir),
        patch("searchat.services.compaction.compact_database", return_value=_failure_result(db_path)),
        patch("searchat.services.compaction.record_compaction_completed") as mock_record,
    ):
        result = run_compact([])

    captured = capsys.readouterr()
    assert result == 1
    assert "Compaction failed" in captured.out
    assert "in use by another process" in captured.out
    mock_record.assert_not_called()


def test_compact_failure_json_output(temp_search_dir: Path, capsys) -> None:
    from searchat.cli.compact_cmd import run_compact

    db_path = temp_search_dir / "data" / "searchat.duckdb"
    with (
        patch("searchat.config.Config.load", return_value=_cfg(temp_search_dir)),
        patch("searchat.config.PathResolver.get_shared_search_dir", return_value=temp_search_dir),
        patch("searchat.services.compaction.compact_database", return_value=_failure_result(db_path)),
        patch("searchat.services.compaction.record_compaction_completed"),
    ):
        result = run_compact(["--json"])

    captured = capsys.readouterr()
    assert result == 1
    payload = json.loads(captured.out)
    assert payload["success"] is False
    assert "in use by another process" in payload["error"]


def test_compact_returns_one_and_prints_error_on_exception(
    temp_search_dir: Path, capsys
) -> None:
    from searchat.cli.compact_cmd import run_compact

    with (
        patch("searchat.config.Config.load", return_value=_cfg(temp_search_dir)),
        patch("searchat.config.PathResolver.get_shared_search_dir", return_value=temp_search_dir),
        patch(
            "searchat.services.compaction.compact_database",
            side_effect=RuntimeError("disk read failed"),
        ),
    ):
        result = run_compact([])

    captured = capsys.readouterr()
    assert result == 1
    assert "disk read failed" in captured.err


def test_compact_in_process_flag_disables_subprocess_isolation(
    temp_search_dir: Path, capsys
) -> None:
    from searchat.cli.compact_cmd import run_compact

    db_path = temp_search_dir / "data" / "searchat.duckdb"
    with (
        patch("searchat.config.Config.load", return_value=_cfg(temp_search_dir)),
        patch("searchat.config.PathResolver.get_shared_search_dir", return_value=temp_search_dir),
        patch(
            "searchat.services.compaction.compact_database", return_value=_success_result(db_path)
        ) as mock_compact,
        patch("searchat.services.compaction.record_compaction_completed"),
    ):
        run_compact(["--in-process"])

    mock_compact.assert_called_once_with(db_path, subprocess_isolated=False)
