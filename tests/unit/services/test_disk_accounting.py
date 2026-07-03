"""Unit tests for `searchat.services.disk_accounting`.

Covers the M6 disk-manager-dashboard acceptance criteria: `du`-equivalent
per-agent size accounting (not restricted to discovered conversation
files), exact indexed/unindexed deltas sourced from `source_file_state`,
Searchat's own labeled self-accounting subdirectories (present or absent),
null-`connector_name` routing via `detect_connector`, per-connector
resilience in `build_disk_accounting_report`, and age-histogram bucketing.
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import duckdb
import pytest

from searchat.services.disk_accounting import (
    AgentDiskUsage,
    DiskAccountingReport,
    _read_indexed_paths_by_connector,
    build_disk_accounting_report,
    compute_agent_disk_usage,
    compute_searchat_self_usage,
)
from searchat.storage.schema import ensure_tables

_AGE_BUCKET_LABELS = ("0-7d", "7-30d", "30-90d", "90-365d", "365d+")
_SELF_ACCOUNTING_LABELS = {
    "index",
    "backups",
    "models",
    "expertise",
    "knowledge_graph",
    "analytics",
    "config",
    "logs",
}


@dataclass
class _FakeConnector:
    """Minimal connector satisfying AgentConnector, with no `watch_dirs`
    method -- exercises `_connector_watch_dirs`'s fallback of deriving watch
    dirs from `discover_files` results' parent directories, the same path
    most connectors without an explicit `watch_dirs` override take.
    """

    name: str
    supported_extensions: tuple[str, ...]
    files: list[Path]

    def discover_files(self, config):
        return list(self.files)

    def can_parse(self, path):
        return path.suffix in self.supported_extensions

    def parse(self, path, embedding_id):
        raise NotImplementedError


class _BrokenNameConnector:
    """Connector whose `.name` access raises.

    `compute_agent_disk_usage` already swallows a raising `discover_files`
    internally (falls back to an empty conversation list), so that alone
    never reaches `build_disk_accounting_report`'s per-connector
    `except Exception: continue` guard. Reading `.name` is the one
    unguarded attribute access that guard actually protects -- it happens
    both in `indexed_by_connector.get(connector.name, ...)` and inside
    `AgentDiskUsage(connector=connector.name, ...)`.
    """

    supported_extensions: tuple[str, ...] = (".broken",)

    @property
    def name(self):
        raise RuntimeError("harness metadata unavailable")

    def discover_files(self, config):
        return []

    def can_parse(self, path):
        return False

    def parse(self, path, embedding_id):
        raise NotImplementedError


def _write(path: Path, size: int) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"x" * size)
    return path


# ---------------------------------------------------------------------------
# Acceptance 1: total_size_bytes is a full `du`-equivalent walk of the
# connector's watch dir, not restricted to discover_files() results.
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_compute_agent_disk_usage_total_size_matches_du_walk_including_non_conversation_files(
    tmp_path: Path,
) -> None:
    watch_dir = tmp_path / "claude"
    conv1 = _write(watch_dir / "conv1.jsonl", 120)
    conv2 = _write(watch_dir / "conv2.jsonl", 340)
    cruft = _write(watch_dir / "state.lock", 57)  # never discovered as a conversation

    connector = _FakeConnector(name="claude", supported_extensions=(".jsonl",), files=[conv1, conv2])
    result = compute_agent_disk_usage(connector, Mock(), indexed_paths=set())

    expected_total = sum(p.stat().st_size for p in (conv1, conv2, cruft))
    assert result.total_size_bytes == expected_total
    assert result.total_file_count == 3
    assert result.conversation_file_count == 2
    # Directly proves the walk is NOT silently scoped to discover_files() results.
    assert result.total_size_bytes > conv1.stat().st_size + conv2.stat().st_size


# ---------------------------------------------------------------------------
# Acceptance 2: unindexed_file_count == N - K exactly.
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_compute_agent_disk_usage_unindexed_count_matches_known_delta_exactly(tmp_path: Path) -> None:
    watch_dir = tmp_path / "vibe"
    files = [_write(watch_dir / f"conv_{i}.json", 10 + i) for i in range(5)]  # N=5
    indexed = {str(files[0]), str(files[1])}  # K=2

    connector = _FakeConnector(name="vibe", supported_extensions=(".json",), files=files)
    result = compute_agent_disk_usage(connector, Mock(), indexed_paths=indexed)

    assert result.conversation_file_count == 5
    assert result.indexed_file_count == 2
    assert result.unindexed_file_count == 3  # N - K, exactly
    assert result.indexed_size_bytes == files[0].stat().st_size + files[1].stat().st_size
    assert result.unindexed_size_bytes == sum(f.stat().st_size for f in files[2:])


@pytest.mark.unit
def test_build_disk_accounting_report_unindexed_count_matches_db_seeded_delta_exactly(
    temp_search_dir: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    watch_dir = tmp_path / "claude_home"
    files = [_write(watch_dir / f"conv_{i}.jsonl", 50 + i) for i in range(5)]  # N=5
    indexed_subset = files[:2]  # K=2; files[2:] never appear in source_file_state at all

    db_path = temp_search_dir / "data" / "searchat.duckdb"
    conn = duckdb.connect(str(db_path))
    ensure_tables(conn)
    now = datetime.now()
    for f in indexed_subset:
        conn.execute(
            "INSERT INTO source_file_state "
            "(file_path, conversation_id, project_id, connector_name, status, file_size, updated_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            [str(f), f"conv-{f.name}", "p1", "claude", "indexed", f.stat().st_size, now],
        )
    conn.close()  # release the write lock before build_disk_accounting_report opens read-only

    connector = _FakeConnector(name="claude", supported_extensions=(".jsonl",), files=files)
    monkeypatch.setattr("searchat.services.disk_accounting.get_connectors", lambda: (connector,))

    config = Mock()
    config.storage.resolve_duckdb_path.return_value = db_path

    report = build_disk_accounting_report(temp_search_dir, config)

    assert len(report.agents) == 1
    agent = report.agents[0]
    assert agent.conversation_file_count == 5
    assert agent.indexed_file_count == 2
    assert agent.unindexed_file_count == 3  # N - K, exactly
    assert agent.indexed_size_bytes == sum(f.stat().st_size for f in indexed_subset)


# ---------------------------------------------------------------------------
# Acceptance 3: compute_searchat_self_usage's fixed label set, present and
# absent subdirectories.
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_compute_searchat_self_usage_includes_all_labels_with_existing_subdirectories(
    temp_search_dir: Path,
) -> None:
    _write(temp_search_dir / "data" / "searchat.duckdb", 1000)  # index -> data/
    _write(temp_search_dir / "backups" / "backup1" / "manifest.json", 40)
    _write(temp_search_dir / "models" / "all-MiniLM-L6-v2.bin", 2048)
    _write(temp_search_dir / "expertise" / "graph.json", 512)
    # knowledge_graph/, analytics/, logs/ intentionally left absent; config/
    # exists (created by temp_search_dir) but stays empty.

    result = compute_searchat_self_usage(temp_search_dir)
    by_label = {sub.label: sub for sub in result.subdirectories}

    assert {sub.label for sub in result.subdirectories} == _SELF_ACCOUNTING_LABELS

    assert by_label["index"].exists is True
    assert by_label["index"].file_count == 1
    assert by_label["index"].total_size_bytes == 1000

    assert by_label["backups"].exists is True
    assert by_label["backups"].total_size_bytes == 40

    assert by_label["models"].exists is True
    assert by_label["models"].total_size_bytes == 2048

    assert by_label["expertise"].exists is True
    assert by_label["expertise"].total_size_bytes == 512

    assert by_label["config"].exists is True
    assert by_label["config"].file_count == 0

    assert by_label["knowledge_graph"].exists is False
    assert by_label["knowledge_graph"].total_size_bytes == 0
    assert by_label["logs"].exists is False
    assert by_label["logs"].file_count == 0

    assert result.total_size_bytes == 1000 + 40 + 2048 + 512
    assert result.total_file_count == 4


@pytest.mark.unit
def test_compute_searchat_self_usage_reports_zero_without_raising_when_search_dir_absent(
    tmp_path: Path,
) -> None:
    missing_search_dir = tmp_path / "never_initialized" / ".searchat"

    result = compute_searchat_self_usage(missing_search_dir)

    assert {sub.label for sub in result.subdirectories} == _SELF_ACCOUNTING_LABELS
    for sub in result.subdirectories:
        assert sub.exists is False
        assert sub.total_size_bytes == 0
        assert sub.file_count == 0
    assert result.total_size_bytes == 0
    assert result.total_file_count == 0


# ---------------------------------------------------------------------------
# Acceptance 4: null/empty connector_name rows are routed via
# detect_connector, including its ValueError -> "unknown" fallback.
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_read_indexed_paths_by_connector_routes_null_connector_name_via_detect_connector(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    db_path = tmp_path / "state.duckdb"
    conn = duckdb.connect(str(db_path))
    ensure_tables(conn)
    now = datetime.now()
    rows = [
        ("/watch/claude/conv1.jsonl", "claude"),  # normal: connector_name already set
        ("/watch/vibe/session.json", None),  # null connector_name -> detect_connector fallback
        ("/watch/mystery/file.xyz", ""),  # empty connector_name -> detect_connector raises ValueError
    ]
    for i, (path, connector_name) in enumerate(rows):
        conn.execute(
            "INSERT INTO source_file_state "
            "(file_path, conversation_id, project_id, connector_name, status, file_size, updated_at) "
            "VALUES (?, ?, ?, ?, 'indexed', ?, ?)",
            [path, f"c{i}", "p1", connector_name, 10, now],
        )
    conn.close()

    def fake_detect_connector(path: Path):
        if path.suffix == ".json":
            return SimpleNamespace(name="vibe")
        raise ValueError(f"No connector found for {path}")

    monkeypatch.setattr("searchat.services.disk_accounting.detect_connector", fake_detect_connector)

    result = _read_indexed_paths_by_connector(db_path)

    assert result["claude"] == {"/watch/claude/conv1.jsonl"}
    assert result["vibe"] == {"/watch/vibe/session.json"}
    assert result["unknown"] == {"/watch/mystery/file.xyz"}


# ---------------------------------------------------------------------------
# Acceptance 5: a connector whose accounting raises is skipped, not fatal.
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_build_disk_accounting_report_skips_connector_whose_accounting_raises(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    watch_dir = tmp_path / "claude_home"
    conv = _write(watch_dir / "conv.jsonl", 42)

    good_connector = _FakeConnector(name="claude", supported_extensions=(".jsonl",), files=[conv])
    broken_connector = _BrokenNameConnector()

    monkeypatch.setattr(
        "searchat.services.disk_accounting.get_connectors",
        lambda: (good_connector, broken_connector),
    )

    config = Mock()
    config.storage.resolve_duckdb_path.return_value = tmp_path / "missing.duckdb"

    report = build_disk_accounting_report(tmp_path, config)

    assert [agent.connector for agent in report.agents] == ["claude"]
    assert report.agents[0].total_size_bytes == 42


# ---------------------------------------------------------------------------
# Acceptance 6: age histogram bucketing, and None ages with zero discovered
# conversation files (never 0 or a crash).
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_compute_agent_disk_usage_buckets_known_file_ages_into_correct_labels(tmp_path: Path) -> None:
    watch_dir = tmp_path / "codex"
    reference = datetime(2026, 1, 1, 12, 0, 0)
    age_days_by_index = {0: 3, 1: 15, 2: 60, 3: 200, 4: 400}
    expected_label_by_index = {0: "0-7d", 1: "7-30d", 2: "30-90d", 3: "90-365d", 4: "365d+"}

    files = []
    for i, age_days in age_days_by_index.items():
        f = _write(watch_dir / f"conv_{i}.jsonl", 1)
        mtime = (reference - timedelta(days=age_days)).timestamp()
        os.utime(f, (mtime, mtime))
        files.append(f)

    connector = _FakeConnector(name="codex", supported_extensions=(".jsonl",), files=files)
    result = compute_agent_disk_usage(connector, Mock(), indexed_paths=set(), now=reference)

    expected_histogram = {label: 0 for label in _AGE_BUCKET_LABELS}
    for label in expected_label_by_index.values():
        expected_histogram[label] += 1

    assert result.age_histogram == expected_histogram
    assert result.oldest_conversation_age_days == pytest.approx(400.0, abs=0.5)
    assert result.newest_conversation_age_days == pytest.approx(3.0, abs=0.5)


@pytest.mark.unit
def test_compute_agent_disk_usage_ages_are_none_with_zero_discovered_files(tmp_path: Path) -> None:
    watch_dir = tmp_path / "empty_agent"
    _write(watch_dir / "not_a_conversation.log", 5)  # on disk, never discovered

    connector = _FakeConnector(name="empty_agent", supported_extensions=(".jsonl",), files=[])
    result = compute_agent_disk_usage(connector, Mock(), indexed_paths=set())

    assert result.conversation_file_count == 0
    assert result.oldest_conversation_age_days is None
    assert result.newest_conversation_age_days is None
    assert result.age_histogram == {label: 0 for label in _AGE_BUCKET_LABELS}
    assert result.indexed_file_count == 0
    assert result.unindexed_file_count == 0


# ---------------------------------------------------------------------------
# Supporting coverage: report assembly wiring and to_dict() serialization.
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_build_disk_accounting_report_assembles_agents_and_searchat_self(
    temp_search_dir: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    watch_dir = tmp_path / "claude_home"
    conv = _write(watch_dir / "conv.jsonl", 10)
    connector = _FakeConnector(name="claude", supported_extensions=(".jsonl",), files=[conv])
    monkeypatch.setattr("searchat.services.disk_accounting.get_connectors", lambda: (connector,))

    config = Mock()
    config.storage.resolve_duckdb_path.return_value = temp_search_dir / "data" / "missing.duckdb"

    report = build_disk_accounting_report(temp_search_dir, config)

    assert isinstance(report, DiskAccountingReport)
    assert len(report.agents) == 1
    assert report.agents[0].connector == "claude"
    assert report.searchat_self.search_dir == str(temp_search_dir)
    datetime.fromisoformat(report.generated_at)  # ISO-parseable, never raises

    payload = report.to_dict()
    assert payload["agents"][0]["connector"] == "claude"
    assert payload["searchat_self"]["search_dir"] == str(temp_search_dir)
    assert payload["generated_at"] == report.generated_at


@pytest.mark.unit
def test_agent_disk_usage_to_dict_serializes_all_fields() -> None:
    usage = AgentDiskUsage(
        connector="claude",
        watch_dirs=("/a", "/b"),
        total_size_bytes=10,
        total_file_count=2,
        conversation_file_count=2,
        indexed_file_count=1,
        indexed_size_bytes=5,
        unindexed_file_count=1,
        unindexed_size_bytes=5,
        oldest_conversation_age_days=10.0,
        newest_conversation_age_days=1.0,
        age_histogram={"0-7d": 1, "7-30d": 1, "30-90d": 0, "90-365d": 0, "365d+": 0},
    )

    payload = usage.to_dict()

    assert payload["watch_dirs"] == ["/a", "/b"]
    assert payload["age_histogram"] == {"0-7d": 1, "7-30d": 1, "30-90d": 0, "90-365d": 0, "365d+": 0}
    assert payload["oldest_conversation_age_days"] == 10.0
    assert payload["connector"] == "claude"


# ---------------------------------------------------------------------------
# Bug fix: `connection=` kwarg lets a caller reuse an already-open DuckDB
# connection (the live `searchat-web` server's `UnifiedStorage.connection`)
# instead of opening a second file connection, which DuckDB refuses once
# the first connection has non-default config (e.g. `memory_limit`) --
# mirroring the pre-existing `/api/health` storage-section failure for the
# identical reason.
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_read_indexed_paths_by_connector_uses_passed_connection_instead_of_opening_new_one(
    tmp_path: Path,
) -> None:
    db_path = tmp_path / "state.duckdb"
    conn = duckdb.connect(str(db_path))
    ensure_tables(conn)
    now = datetime.now()
    conn.execute(
        "INSERT INTO source_file_state "
        "(file_path, conversation_id, project_id, connector_name, status, file_size, updated_at) "
        "VALUES (?, ?, ?, ?, 'indexed', ?, ?)",
        ["/watch/claude/conv1.jsonl", "c1", "p1", "claude", 10, now],
    )

    result = _read_indexed_paths_by_connector(db_path, connection=conn)
    conn.close()

    assert result == {"claude": {"/watch/claude/conv1.jsonl"}}


@pytest.mark.unit
def test_read_indexed_paths_by_connector_reuses_connection_with_mismatched_config_in_same_process(
    tmp_path: Path,
) -> None:
    """Regression test for the reproduced `GET /api/disk` 500.

    A second `duckdb.connect(db_path, read_only=True)` to a file that
    already has an open, non-default-config connection in the same process
    raises `duckdb.ConnectionException`. Passing that same connection
    through `connection=` must route through `connection.cursor()` instead,
    so no second file connection is ever attempted.
    """
    db_path = tmp_path / "state.duckdb"
    con = duckdb.connect(str(db_path))
    con.execute("PRAGMA memory_limit='512MB'")  # mirrors UnifiedStorage.__init__
    ensure_tables(con)
    now = datetime.now()
    con.execute(
        "INSERT INTO source_file_state "
        "(file_path, conversation_id, project_id, connector_name, status, file_size, updated_at) "
        "VALUES (?, ?, ?, ?, 'indexed', ?, ?)",
        ["/watch/vibe/session.json", "c1", "p1", "vibe", 10, now],
    )

    # The old code path (`duckdb.connect(db_path, read_only=True)` while `con`
    # is still open with non-default config) is exactly what raised in
    # production; asserting that here documents the failure this closes.
    with pytest.raises(duckdb.Error):
        duckdb.connect(str(db_path), read_only=True)

    result = _read_indexed_paths_by_connector(db_path, connection=con)
    con.close()

    assert result == {"vibe": {"/watch/vibe/session.json"}}


@pytest.mark.unit
def test_build_disk_accounting_report_threads_connection_kwarg_to_indexed_paths_lookup(
    temp_search_dir: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    watch_dir = tmp_path / "claude_home"
    conv = _write(watch_dir / "conv.jsonl", 10)
    connector = _FakeConnector(name="claude", supported_extensions=(".jsonl",), files=[conv])
    monkeypatch.setattr("searchat.services.disk_accounting.get_connectors", lambda: (connector,))

    db_path = temp_search_dir / "data" / "searchat.duckdb"
    config = Mock()
    config.storage.resolve_duckdb_path.return_value = db_path

    sentinel_connection = Mock(spec=duckdb.DuckDBPyConnection)
    received: dict[str, object] = {}

    def fake_read_indexed_paths_by_connector(path, *, connection=None):
        received["db_path"] = path
        received["connection"] = connection
        return {}

    monkeypatch.setattr(
        "searchat.services.disk_accounting._read_indexed_paths_by_connector",
        fake_read_indexed_paths_by_connector,
    )

    build_disk_accounting_report(temp_search_dir, config, connection=sentinel_connection)

    assert received["connection"] is sentinel_connection
    assert received["db_path"] == db_path
