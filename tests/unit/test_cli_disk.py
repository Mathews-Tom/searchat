"""Unit tests for `searchat disk` CLI command."""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import duckdb
import pytest


def _cfg(search_dir: Path) -> SimpleNamespace:
    """Minimal Config stand-in exposing only what run_disk touches."""
    return SimpleNamespace(
        storage=SimpleNamespace(resolve_duckdb_path=lambda _search_dir: search_dir / "data" / "searchat.duckdb")
    )


def _fake_connector(name: str, files: list[Path], watch_dir: Path) -> SimpleNamespace:
    """Minimal AgentConnector stand-in exposing only what disk accounting touches."""
    return SimpleNamespace(
        name=name,
        discover_files=lambda _config: files,
        watch_dirs=lambda _config: [watch_dir],
    )


def test_disk_help_text(capsys) -> None:
    from searchat.cli.disk_cmd import run_disk

    with pytest.raises(SystemExit) as exc_info:
        run_disk(["--help"])
    assert exc_info.value.code == 0

    captured = capsys.readouterr()
    assert "disk" in captured.out.lower()
    assert "--json" in captured.out


def test_disk_table_output_with_no_connectors_shows_friendly_message_and_self_usage(
    temp_search_dir: Path, capsys
) -> None:
    from searchat.cli.disk_cmd import run_disk

    with (
        patch("searchat.config.Config.load", return_value=_cfg(temp_search_dir)),
        patch("searchat.config.PathResolver.get_shared_search_dir", return_value=temp_search_dir),
        patch("searchat.services.disk_accounting.get_connectors", return_value=()),
    ):
        result = run_disk([])

    captured = capsys.readouterr()
    assert result == 0
    assert "No registered connectors discovered any files." in captured.out
    assert "Searchat Self" in captured.out
    assert "index" in captured.out
    assert "backups" in captured.out
    assert "models" in captured.out
    assert "expertise" in captured.out
    assert "Total Searchat footprint:" in captured.out


def test_disk_table_output_shows_connector_usage(
    temp_search_dir: Path, tmp_path: Path, capsys, monkeypatch
) -> None:
    from searchat.cli.disk_cmd import run_disk

    # Wide enough console so an 8-column table doesn't ellipsize cell text.
    monkeypatch.setenv("COLUMNS", "200")

    agent_dir = tmp_path / "fake_agent_files"
    agent_dir.mkdir(parents=True, exist_ok=True)
    files = []
    for i in range(3):
        conv_file = agent_dir / f"conv{i}.jsonl"
        conv_file.write_bytes(b"x" * 1024)
        files.append(conv_file)

    data_dir = temp_search_dir / "data"
    data_dir.mkdir(parents=True, exist_ok=True)
    db_path = data_dir / "searchat.duckdb"
    con = duckdb.connect(str(db_path))
    con.execute("CREATE TABLE source_file_state(connector_name VARCHAR, file_path VARCHAR, status VARCHAR)")
    con.execute(
        "INSERT INTO source_file_state VALUES (?, ?, 'indexed'), (?, ?, 'indexed')",
        ["fake-agent", str(files[0]), "fake-agent", str(files[1])],
    )
    con.execute("CHECKPOINT")
    con.close()

    connector = _fake_connector("fake-agent", files, agent_dir)

    with (
        patch("searchat.config.Config.load", return_value=_cfg(temp_search_dir)),
        patch("searchat.config.PathResolver.get_shared_search_dir", return_value=temp_search_dir),
        patch("searchat.services.disk_accounting.get_connectors", return_value=(connector,)),
    ):
        result = run_disk([])

    captured = capsys.readouterr()
    assert result == 0
    assert "Agents" in captured.out
    assert "fake-agent" in captured.out
    assert "3.0 KB" in captured.out  # total_size_bytes: 3 files x 1024 bytes
    assert "Indexed" in captured.out
    assert "Unindexed" in captured.out


def test_disk_json_output_matches_documented_schema(
    temp_search_dir: Path, tmp_path: Path, capsys
) -> None:
    from searchat.cli.disk_cmd import run_disk

    agent_dir = tmp_path / "json_agent_files"
    agent_dir.mkdir(parents=True, exist_ok=True)
    files = []
    for i in range(2):
        conv_file = agent_dir / f"conv{i}.jsonl"
        conv_file.write_bytes(b"x" * 512)
        files.append(conv_file)

    data_dir = temp_search_dir / "data"
    data_dir.mkdir(parents=True, exist_ok=True)
    db_path = data_dir / "searchat.duckdb"
    con = duckdb.connect(str(db_path))
    con.execute("CREATE TABLE source_file_state(connector_name VARCHAR, file_path VARCHAR, status VARCHAR)")
    con.execute(
        "INSERT INTO source_file_state VALUES (?, ?, 'indexed')",
        ["json-agent", str(files[0])],
    )
    con.execute("CHECKPOINT")
    con.close()

    connector = _fake_connector("json-agent", files, agent_dir)

    with (
        patch("searchat.config.Config.load", return_value=_cfg(temp_search_dir)),
        patch("searchat.config.PathResolver.get_shared_search_dir", return_value=temp_search_dir),
        patch("searchat.services.disk_accounting.get_connectors", return_value=(connector,)),
    ):
        result = run_disk(["--json"])

    captured = capsys.readouterr()
    assert result == 0
    payload = json.loads(captured.out)

    # Top-level schema.
    assert set(payload.keys()) == {"agents", "searchat_self", "generated_at"}
    assert isinstance(payload["agents"], list)
    assert isinstance(payload["searchat_self"], dict)
    assert isinstance(payload["generated_at"], str)
    datetime.fromisoformat(payload["generated_at"])  # valid ISO-8601 timestamp

    assert len(payload["agents"]) == 1
    agent_entry = payload["agents"][0]
    assert set(agent_entry.keys()) == {
        "connector",
        "watch_dirs",
        "total_size_bytes",
        "total_file_count",
        "conversation_file_count",
        "indexed_file_count",
        "indexed_size_bytes",
        "unindexed_file_count",
        "unindexed_size_bytes",
        "oldest_conversation_age_days",
        "newest_conversation_age_days",
        "age_histogram",
    }
    assert agent_entry["connector"] == "json-agent"
    assert agent_entry["total_file_count"] == 2
    assert agent_entry["conversation_file_count"] == 2
    assert agent_entry["indexed_file_count"] == 1
    assert agent_entry["unindexed_file_count"] == 1
    assert isinstance(agent_entry["age_histogram"], dict)

    self_usage = payload["searchat_self"]
    assert set(self_usage.keys()) == {"search_dir", "subdirectories", "total_size_bytes", "total_file_count"}
    assert isinstance(self_usage["subdirectories"], list)
    labels = {sub["label"] for sub in self_usage["subdirectories"]}
    assert {"index", "backups", "models", "expertise"} <= labels
    for sub in self_usage["subdirectories"]:
        assert set(sub.keys()) == {"label", "path", "exists", "total_size_bytes", "file_count"}


def test_disk_returns_one_and_prints_error_on_failure(temp_search_dir: Path, capsys) -> None:
    from searchat.cli.disk_cmd import run_disk

    with (
        patch("searchat.config.Config.load", return_value=_cfg(temp_search_dir)),
        patch("searchat.config.PathResolver.get_shared_search_dir", return_value=temp_search_dir),
        patch(
            "searchat.services.disk_accounting.build_disk_accounting_report",
            side_effect=RuntimeError("disk accounting failed"),
        ),
    ):
        result = run_disk([])

    captured = capsys.readouterr()
    assert result == 1
    assert "disk accounting failed" in captured.err
