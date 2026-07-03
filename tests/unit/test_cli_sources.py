"""Unit tests for `searchat sources archive` / `searchat sources prune` CLI
commands (`searchat.cli.sources_cmd.run_sources`) -- the M8 verified
archive-then-prune of source conversation files.

`tests/unit/services/test_source_lifecycle.py` covers
`services.source_lifecycle` in isolation. This file covers the CLI layer
on top of it: argument parsing (`--help`, subcommand dispatch, `--json`,
bad `--dry-run` values) and full end-to-end wiring through the real
`Config.load()` / `PathResolver.get_shared_search_dir()` / DuckDB path
resolution -- including a real fixture DuckDB, a real backdated Claude
`.jsonl` file, and the real `ClaudeConnector`, with no mocking of the
lifecycle service itself. The default-dry-run end-to-end test proves the
CLI entry point itself (not just the service function) makes zero
filesystem-destroying writes until `--dry-run=false` is passed.
"""
from __future__ import annotations

import json
import os
from datetime import datetime, timedelta
from pathlib import Path

import duckdb
import pytest

from searchat.cli.sources_cmd import run_sources
from searchat.config import Config, PathResolver
from searchat.core.connectors import registry
from searchat.core.connectors.claude import ClaudeConnector
from searchat.storage.schema import ensure_tables

# ---------------------------------------------------------------------------
# Fixture helpers -- mirror the pattern established in
# tests/unit/services/test_source_lifecycle.py, duplicated locally (rather
# than imported) so this file has no dependency on that one's internals.
# ---------------------------------------------------------------------------


def _write_claude_jsonl(path: Path, num_exchanges: int = 1) -> Path:
    """Write a real, minimal Claude-format JSONL fixture -- the exact shape
    `ClaudeConnector.parse()` expects: `type` in {"user", "assistant"},
    `message.content` as a plain string, and an ISO `timestamp`.

    Each exchange is one user line + one assistant line, so the real
    message count a fresh parse will count is `2 * num_exchanges`.
    """
    base = datetime(2025, 1, 15, 10, 0, 0)
    entries: list[dict[str, object]] = []
    for i in range(num_exchanges):
        entries.append(
            {
                "type": "user",
                "message": {"content": f"Question {i}"},
                "timestamp": (base + timedelta(minutes=2 * i)).isoformat(),
            }
        )
        entries.append(
            {
                "type": "assistant",
                "message": {"content": f"Answer {i}"},
                "timestamp": (base + timedelta(minutes=2 * i, seconds=30)).isoformat(),
            }
        )
    path.write_text("\n".join(json.dumps(entry) for entry in entries) + "\n", encoding="utf-8")
    return path


def _resolve_db_path() -> Path:
    """The exact DuckDB path `run_sources` will resolve at call time,
    given whatever SEARCHAT_DATA_DIR currently is -- computed the same
    way `sources_cmd._run` computes it, so a fixture DB built here is
    found by the real CLI entry point."""
    config = Config.load()
    search_dir = PathResolver.get_shared_search_dir(config)
    return config.storage.resolve_duckdb_path(search_dir)


def _new_db_at(db_path: Path) -> None:
    """Create an empty but fully-migrated fixture DuckDB file at the
    exact path the CLI will look for it."""
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = duckdb.connect(str(db_path))
    try:
        ensure_tables(conn)
    finally:
        conn.close()


def _insert_source_file_state(
    db_path: Path,
    *,
    file_path: str,
    conversation_id: str | None,
    project_id: str = "proj",
    connector_name: str = "claude",
    status: str = "indexed",
    file_size: int = 0,
    file_hash: str | None,
    updated_at: datetime | None = None,
) -> None:
    conn = duckdb.connect(str(db_path))
    try:
        conn.execute(
            "INSERT INTO source_file_state "
            "(file_path, conversation_id, project_id, connector_name, status, "
            "file_size, file_hash, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            [
                file_path,
                conversation_id,
                project_id,
                connector_name,
                status,
                file_size,
                file_hash,
                updated_at or datetime.now(),
            ],
        )
    finally:
        conn.close()


def _insert_conversation(
    db_path: Path,
    *,
    conversation_id: str,
    file_path: str,
    message_count: int,
    project_id: str = "proj",
    title: str = "Test conversation",
    full_text: str = "some indexed text",
    file_hash: str = "unused-in-conversations-lookup",
) -> None:
    now = datetime.now()
    conn = duckdb.connect(str(db_path))
    try:
        conn.execute(
            "INSERT INTO conversations "
            "(conversation_id, project_id, file_path, title, created_at, updated_at, "
            "message_count, full_text, file_hash, indexed_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            [
                conversation_id,
                project_id,
                file_path,
                title,
                now,
                now,
                message_count,
                full_text,
                file_hash,
                now,
            ],
        )
    finally:
        conn.close()


def _sha256(path: Path) -> str:
    import hashlib

    return hashlib.sha256(path.read_bytes()).hexdigest()


def _ensure_claude_connector_registered() -> None:
    """Register the real `ClaudeConnector` exactly once for the whole
    test session -- `registry` is process-global module state, and a
    sibling test module (test_source_lifecycle.py) may have already
    registered it first."""
    if registry.get_connector_by_name("claude") is None:
        registry.register_connector(ClaudeConnector())


# ---------------------------------------------------------------------------
# 1. --help mentions --dry-run and the default-to-true safety framing.
# ---------------------------------------------------------------------------


@pytest.mark.unit
@pytest.mark.parametrize("subcommand", ["archive", "prune"])
def test_help_output_mentions_dry_run_and_default_safety_framing(subcommand: str, capsys) -> None:
    with pytest.raises(SystemExit) as exc_info:
        run_sources([subcommand, "--help"])

    assert exc_info.value.code == 0
    captured = capsys.readouterr()
    normalized = " ".join(captured.out.split())
    assert "--dry-run" in captured.out
    assert "Defaults to true" in normalized
    assert "--dry-run=false" in normalized


# ---------------------------------------------------------------------------
# 2. Invalid / empty subcommand.
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_invalid_subcommand_returns_one_and_prints_usage_to_stderr(capsys) -> None:
    exit_code = run_sources(["bogus"])

    assert exit_code == 1
    captured = capsys.readouterr()
    assert "Usage: searchat sources" in captured.err
    assert captured.out == ""


@pytest.mark.unit
def test_empty_argv_returns_one_and_prints_usage_to_stderr(capsys) -> None:
    exit_code = run_sources([])

    assert exit_code == 1
    captured = capsys.readouterr()
    assert "Usage: searchat sources" in captured.err


# ---------------------------------------------------------------------------
# 3. No indexed files at all (no DuckDB file yet): real Config/PathResolver
#    path, isolated from the real user's ~/.searchat.
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_prune_json_with_no_db_file_prints_empty_array(temp_search_dir: Path, capsys) -> None:
    # `temp_search_dir` pre-creates an empty `.searchat/{data,config,backups}`
    # structure under `tmp_path`, and the autouse `_isolate_searchat_data_dir`
    # fixture (same tmp_path) already points SEARCHAT_DATA_DIR at it -- no
    # DuckDB file exists there, so `run_lifecycle_action` sees a missing db
    # and returns an empty decision list without ever touching the real
    # user's home directory.
    assert not (temp_search_dir / "data" / "searchat.duckdb").exists()

    exit_code = run_sources(["prune", "--json"])

    assert exit_code == 0
    captured = capsys.readouterr()
    assert captured.out.strip() == "[]"
    assert json.loads(captured.out) == []


# ---------------------------------------------------------------------------
# 4. Real end-to-end prune: default dry run first (eligible, no action, file
#    untouched), then --dry-run=false against the SAME fixture (file gone,
#    tombstone written).
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_prune_dry_run_then_real_prune_full_cli_roundtrip(
    tmp_path: Path, monkeypatch, capsys
) -> None:
    monkeypatch.setenv("SEARCHAT_LIFECYCLE_ENABLED_AGENTS", "claude")
    _ensure_claude_connector_registered()

    source_file = _write_claude_jsonl(tmp_path / "conv-cli-prune.jsonl", num_exchanges=2)
    connector = ClaudeConnector()
    real_hash = _sha256(source_file)
    real_message_count = connector.parse(source_file, embedding_id=0).message_count
    conversation_id = source_file.stem

    db_path = _resolve_db_path()
    _new_db_at(db_path)
    _insert_source_file_state(
        db_path,
        file_path=str(source_file),
        conversation_id=conversation_id,
        file_hash=real_hash,
    )
    _insert_conversation(
        db_path,
        conversation_id=conversation_id,
        file_path=str(source_file),
        message_count=real_message_count,
    )

    # Back-date well past the (default) 60-day age threshold so this is the
    # strongest possible dry-run candidate: it passes every gate up to the
    # dry-run check, not one that was refused earlier for an unrelated
    # reason.
    old_mtime = (datetime.now() - timedelta(days=70)).timestamp()
    os.utime(source_file, (old_mtime, old_mtime))
    original_bytes = source_file.read_bytes()

    # --- (a) default dry run: eligible, no action, zero writes ---
    exit_code = run_sources(["prune", "--json"])
    assert exit_code == 0
    captured = capsys.readouterr()
    decisions = json.loads(captured.out)
    assert len(decisions) == 1
    assert decisions[0]["eligible"] is True
    assert decisions[0]["action_taken"] is None

    assert source_file.exists()
    assert source_file.read_bytes() == original_bytes

    # --- (b) --dry-run=false against the same fixture: real prune ---
    exit_code = run_sources(["prune", "--dry-run=false", "--json"])
    assert exit_code == 0
    captured = capsys.readouterr()
    decisions = json.loads(captured.out)
    assert len(decisions) == 1
    decision = decisions[0]
    assert decision["eligible"] is True
    assert decision["action_taken"] == "prune"
    assert decision["tombstone_path"] is not None

    assert not source_file.exists()

    tombstone_path = Path(decision["tombstone_path"])
    assert tombstone_path.exists()
    lines = tombstone_path.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 1
    entry = json.loads(lines[0])
    assert entry["action"] == "prune"
    assert entry["conversation_id"] == conversation_id


# ---------------------------------------------------------------------------
# 5. Real end-to-end archive: --dry-run=false, non-JSON rich console output.
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_archive_dry_run_false_full_cli_roundtrip_rich_output(
    tmp_path: Path, monkeypatch, capsys
) -> None:
    monkeypatch.setenv("SEARCHAT_LIFECYCLE_ENABLED_AGENTS", "claude")
    _ensure_claude_connector_registered()

    source_file = _write_claude_jsonl(tmp_path / "conv-cli-archive.jsonl", num_exchanges=2)
    connector = ClaudeConnector()
    real_hash = _sha256(source_file)
    real_message_count = connector.parse(source_file, embedding_id=0).message_count
    conversation_id = source_file.stem

    db_path = _resolve_db_path()
    _new_db_at(db_path)
    _insert_source_file_state(
        db_path,
        file_path=str(source_file),
        conversation_id=conversation_id,
        file_hash=real_hash,
    )
    _insert_conversation(
        db_path,
        conversation_id=conversation_id,
        file_path=str(source_file),
        message_count=real_message_count,
    )

    old_mtime = (datetime.now() - timedelta(days=70)).timestamp()
    os.utime(source_file, (old_mtime, old_mtime))

    exit_code = run_sources(["archive", "--dry-run=false"])

    assert exit_code == 0
    captured = capsys.readouterr()
    assert "archived" in captured.out

    assert not source_file.exists()
    archived_path = source_file.with_name(source_file.name + ".zst")
    assert archived_path.exists()


# ---------------------------------------------------------------------------
# 6. Bad --dry-run value: argparse's own validation rejects it.
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_invalid_dry_run_value_exits_non_zero_via_argparse_validation(capsys) -> None:
    with pytest.raises(SystemExit) as exc_info:
        run_sources(["prune", "--dry-run=maybe"])

    assert exc_info.value.code != 0
    captured = capsys.readouterr()
    assert "--dry-run" in captured.err
