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
import shutil
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import duckdb
import pytest

from searchat.services.dedup_detection import DuplicateSuggestion
from searchat.services.disk_accounting import (
    KNOWN_CRUFT_PATTERNS,
    AgentDiskUsage,
    CruftFinding,
    CruftPattern,
    DiskAccountingReport,
    SearchatSelfUsage,
    _read_indexed_paths_by_connector,
    build_disk_accounting_report,
    compute_agent_disk_usage,
    compute_searchat_self_usage,
    detect_cruft,
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


# ---------------------------------------------------------------------------
# M7 acceptance: cruft advisor detection primitives (CruftPattern,
# CruftFinding, KNOWN_CRUFT_PATTERNS, detect_cruft). Report-only -- nothing
# below ever deletes anything, and a real conversation-bearing path must
# never be flagged.
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_detect_cruft_matches_known_patterns_with_exact_sizes_and_never_flags_conversations(
    tmp_path: Path,
) -> None:
    fake_home = tmp_path / "home"
    log_db = _write(fake_home / ".codex" / "logs_2.sqlite", 4096)
    plugin1 = _write(fake_home / ".claude" / "plugins" / "one.json", 100)
    plugin2 = _write(fake_home / ".claude" / "plugins" / "two.json", 250)
    plugin3 = _write(fake_home / ".claude" / "plugins" / "nested" / "three.bin", 75)
    conversation = _write(
        fake_home / ".codex" / "sessions" / "some-conversation.jsonl", 999
    )

    results = detect_cruft(home=fake_home)

    by_glob = {finding.path_glob: finding for finding in results}
    assert by_glob[".codex/logs_2.sqlite"].total_size_bytes == log_db.stat().st_size
    assert by_glob[".codex/logs_2.sqlite"].file_count == 1
    assert by_glob[".claude/plugins"].total_size_bytes == sum(
        p.stat().st_size for p in (plugin1, plugin2, plugin3)
    )
    assert by_glob[".claude/plugins"].file_count == 3
    assert sum(1 for f in results if f.path_glob == ".codex/logs_2.sqlite") == 1
    assert sum(1 for f in results if f.path_glob == ".claude/plugins") == 1
    assert all(finding.path != str(conversation) for finding in results)
    # Registry patterns whose target was never created contribute no finding
    # at all -- not a zero-sized one.
    assert not any(f.path_glob == ".omp/cache" for f in results)
    assert not any(f.path_glob == ".cursor/extensions" for f in results)


@pytest.mark.unit
def test_detect_cruft_results_sorted_largest_first(tmp_path: Path) -> None:
    fake_home = tmp_path / "home"
    _write(fake_home / ".codex" / "logs_2.sqlite", 500)
    _write(fake_home / ".omp" / "stats.db", 9000)
    _write(fake_home / ".claude" / "shell-snapshots" / "a.txt", 2000)
    _write(fake_home / ".claude" / "shell-snapshots" / "b.txt", 1000)  # dir totals 3000
    _write(fake_home / ".omp" / "logs" / "one.log", 100)  # dir totals 100

    results = detect_cruft(home=fake_home)

    assert len(results) == 4
    sizes = [finding.total_size_bytes for finding in results]
    assert len(set(sizes)) == 4  # distinct known sizes, not a coincidental tie
    assert all(sizes[i] >= sizes[i + 1] for i in range(len(sizes) - 1))


@pytest.mark.unit
def test_detect_cruft_home_none_defaults_to_path_home(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    fake_home = tmp_path / "home"
    _write(fake_home / ".codex" / "logs_2.sqlite", 321)
    monkeypatch.setattr(Path, "home", lambda: fake_home)

    explicit = detect_cruft(home=fake_home)
    defaulted = detect_cruft()

    assert defaulted == explicit
    assert len(defaulted) == 1


@pytest.mark.unit
def test_detect_cruft_skips_symlinked_match(tmp_path: Path) -> None:
    fake_home = tmp_path / "home"
    real_target_dir = (tmp_path / "real_target").resolve()
    _write(real_target_dir / "big.bin", 5000)
    symlink_path = fake_home / ".omp" / "cache"
    symlink_path.parent.mkdir(parents=True, exist_ok=True)
    symlink_path.symlink_to(real_target_dir)

    results = detect_cruft(home=fake_home)

    assert not any(finding.path_glob == ".omp/cache" for finding in results)


@pytest.mark.unit
def test_detect_cruft_custom_patterns_override_registry(tmp_path: Path) -> None:
    fake_home = tmp_path / "home"
    custom_file = _write(fake_home / "custom" / "thing", 42)
    custom_pattern = CruftPattern(
        path_glob="custom/thing", label="Custom", explanation="A custom test pattern."
    )

    results = detect_cruft(home=fake_home, patterns=(custom_pattern,))

    assert len(results) == 1
    finding = results[0]
    assert finding.label == "Custom"
    assert finding.path_glob == "custom/thing"
    assert finding.explanation == "A custom test pattern."
    assert finding.cleanup_hint is None
    assert finding.total_size_bytes == custom_file.stat().st_size
    assert finding.file_count == 1


@pytest.mark.unit
def test_cruft_finding_to_dict_serializes_all_seven_fields() -> None:
    finding = CruftFinding(
        label="Test Label",
        path="/fake/home/.tool/cruft",
        path_glob=".tool/cruft",
        explanation="A fabricated finding for serialization testing.",
        cleanup_hint="tool cache clear",
        total_size_bytes=123456,
        file_count=7,
    )

    payload = finding.to_dict()

    assert payload == {
        "label": "Test Label",
        "path": "/fake/home/.tool/cruft",
        "path_glob": ".tool/cruft",
        "explanation": "A fabricated finding for serialization testing.",
        "cleanup_hint": "tool cache clear",
        "total_size_bytes": 123456,
        "file_count": 7,
    }


@pytest.mark.unit
def test_known_cruft_patterns_registry_entries_are_well_formed_and_unique() -> None:
    assert len(KNOWN_CRUFT_PATTERNS) > 0
    for pattern in KNOWN_CRUFT_PATTERNS:
        assert pattern.path_glob
        assert pattern.label
        assert pattern.explanation

    globs = [pattern.path_glob for pattern in KNOWN_CRUFT_PATTERNS]
    assert len(globs) == len(set(globs))


# ---------------------------------------------------------------------------
# M7 acceptance: cruft findings wired into the unified report
# (build_disk_accounting_report, DiskAccountingReport.cruft_findings) plus
# the milestone's hard mutation-guard acceptance bar -- a test mocking
# os.remove/shutil.rmtree to raise on any call must pass, proving no code
# path in this milestone can ever delete or modify anything on disk.
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_build_disk_accounting_report_wires_cruft_findings_into_report(
    temp_search_dir: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    watch_dir = tmp_path / "claude_home"
    conv = _write(watch_dir / "conv.jsonl", 10)
    connector = _FakeConnector(
        name="claude", supported_extensions=(".jsonl",), files=[conv]
    )
    monkeypatch.setattr(
        "searchat.services.disk_accounting.get_connectors", lambda: (connector,)
    )

    fixed_findings = (
        CruftFinding(
            label="Codex CLI log database",
            path="/fake/home/.codex/logs_2.sqlite",
            path_glob=".codex/logs_2.sqlite",
            explanation="fabricated for this test",
            cleanup_hint=None,
            total_size_bytes=4096,
            file_count=1,
        ),
        CruftFinding(
            label="Claude Code plugins",
            path="/fake/home/.claude/plugins",
            path_glob=".claude/plugins",
            explanation="fabricated for this test",
            cleanup_hint="claude plugins clean",
            total_size_bytes=2048,
            file_count=3,
        ),
    )
    monkeypatch.setattr(
        "searchat.services.disk_accounting.detect_cruft", lambda: fixed_findings
    )

    config = Mock()
    config.storage.resolve_duckdb_path.return_value = (
        temp_search_dir / "data" / "missing.duckdb"
    )

    report = build_disk_accounting_report(temp_search_dir, config)

    assert report.cruft_findings == fixed_findings
    assert report.to_dict()["cruft_findings"] == [
        finding.to_dict() for finding in fixed_findings
    ]


@pytest.mark.unit
def test_build_disk_accounting_report_resilient_when_detect_cruft_raises(
    temp_search_dir: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """One bad subsystem (the cruft scan) never fails the whole report -- mirrors the
    per-connector resilience contract in
    test_build_disk_accounting_report_skips_connector_whose_accounting_raises.
    """
    watch_dir = tmp_path / "claude_home"
    conv = _write(watch_dir / "conv.jsonl", 10)
    connector = _FakeConnector(
        name="claude", supported_extensions=(".jsonl",), files=[conv]
    )
    monkeypatch.setattr(
        "searchat.services.disk_accounting.get_connectors", lambda: (connector,)
    )

    def _raise() -> tuple[CruftFinding, ...]:
        raise RuntimeError("cruft scan blew up")

    monkeypatch.setattr("searchat.services.disk_accounting.detect_cruft", _raise)

    config = Mock()
    config.storage.resolve_duckdb_path.return_value = (
        temp_search_dir / "data" / "missing.duckdb"
    )

    report = build_disk_accounting_report(temp_search_dir, config)

    assert report.cruft_findings == ()
    assert len(report.agents) == 1  # the rest of the report still assembles


@pytest.mark.unit
def test_disk_accounting_report_cruft_findings_defaults_to_empty_tuple() -> None:
    """Omitting `cruft_findings` entirely keeps pre-M7 direct constructions working."""
    report = DiskAccountingReport(
        agents=(),
        searchat_self=SearchatSelfUsage(
            search_dir="/home/user/.searchat",
            subdirectories=(),
            total_size_bytes=0,
            total_file_count=0,
        ),
        generated_at="2026-07-03T12:00:00",
    )

    assert report.cruft_findings == ()
    assert report.to_dict()["cruft_findings"] == []


@pytest.mark.unit
def test_detect_cruft_and_build_disk_accounting_report_never_call_os_remove_or_shutil_rmtree(
    temp_search_dir: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The milestone's hard acceptance bar: mocking os.remove/shutil.rmtree to raise on
    any call must never trip, for detect_cruft() alone AND for the full
    build_disk_accounting_report() -> cruft-findings path -- proving no code path in
    this milestone can ever delete or modify anything on disk.
    """
    fake_home = tmp_path / "home"
    log_db = _write(fake_home / ".codex" / "logs_2.sqlite", 4096)
    plugin1 = _write(fake_home / ".claude" / "plugins" / "one.json", 100)
    plugin2 = _write(fake_home / ".claude" / "plugins" / "two.json", 250)
    stats_db = _write(fake_home / ".omp" / "stats.db", 512)

    remove_guard = Mock(
        side_effect=AssertionError("detect_cruft must never call os.remove")
    )
    rmtree_guard = Mock(
        side_effect=AssertionError("detect_cruft must never call shutil.rmtree")
    )
    monkeypatch.setattr(os, "remove", remove_guard)
    monkeypatch.setattr(shutil, "rmtree", rmtree_guard)

    # (i) detect_cruft() alone completes without tripping either guard, and (ii) it
    # returns the real findings the fixture created -- proving the guard didn't
    # accidentally block a legitimate read too (which would be a false-negative pass).
    results = detect_cruft(home=fake_home)

    assert len(results) == 3
    by_glob = {finding.path_glob: finding for finding in results}
    assert by_glob[".codex/logs_2.sqlite"].total_size_bytes == log_db.stat().st_size
    assert by_glob[".claude/plugins"].total_size_bytes == (
        plugin1.stat().st_size + plugin2.stat().st_size
    )
    assert by_glob[".omp/stats.db"].total_size_bytes == stats_db.stat().st_size
    remove_guard.assert_not_called()
    rmtree_guard.assert_not_called()

    # Full build_disk_accounting_report() -> cruft-findings path, with detect_cruft's
    # real home=None default (Path.home is patched to the fixture tree, not
    # detect_cruft itself -- mocking detect_cruft away would defeat the point of this
    # test) and both guards still active.
    monkeypatch.setattr(Path, "home", lambda: fake_home)
    monkeypatch.setattr("searchat.services.disk_accounting.get_connectors", lambda: ())

    config = Mock()
    config.storage.resolve_duckdb_path.return_value = (
        temp_search_dir / "data" / "missing.duckdb"
    )

    report = build_disk_accounting_report(temp_search_dir, config)

    assert len(report.cruft_findings) == 3
    report_by_glob = {finding.path_glob: finding for finding in report.cruft_findings}
    assert (
        report_by_glob[".codex/logs_2.sqlite"].total_size_bytes == log_db.stat().st_size
    )
    assert report_by_glob[".claude/plugins"].total_size_bytes == (
        plugin1.stat().st_size + plugin2.stat().st_size
    )
    assert report_by_glob[".omp/stats.db"].total_size_bytes == stats_db.stat().st_size
    remove_guard.assert_not_called()
    rmtree_guard.assert_not_called()


# ---------------------------------------------------------------------------
# M11 acceptance: cross-connector duplicate suggestions wired into the
# unified report (build_disk_accounting_report, DiskAccountingReport.
# duplicate_suggestions), report-only, resilient to a failing dedup scan.
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_build_disk_accounting_report_wires_duplicate_suggestions_into_report(
    temp_search_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        "searchat.services.disk_accounting.get_connectors", lambda: ()
    )

    fixed_suggestions = (
        DuplicateSuggestion(
            conversation_id_a="claude-conv-1",
            connector_a="claude",
            title_a="Debugging the auth flow",
            conversation_id_b="codex-conv-1",
            connector_b="codex",
            title_b="Debugging the auth flow",
            similarity=0.97,
        ),
    )
    monkeypatch.setattr(
        "searchat.services.disk_accounting.find_near_duplicates",
        lambda *args, **kwargs: fixed_suggestions,
    )

    config = Mock()
    config.storage.resolve_duckdb_path.return_value = (
        temp_search_dir / "data" / "missing.duckdb"
    )
    config.dedup.similarity_threshold = 0.92

    report = build_disk_accounting_report(temp_search_dir, config)

    assert report.duplicate_suggestions == fixed_suggestions
    assert report.to_dict()["duplicate_suggestions"] == [
        suggestion.to_dict() for suggestion in fixed_suggestions
    ]


@pytest.mark.unit
def test_build_disk_accounting_report_passes_dedup_config_threshold_and_connection(
    temp_search_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """`build_disk_accounting_report` threads `config.dedup.similarity_threshold`
    and the live `connection` straight through to `find_near_duplicates`."""
    monkeypatch.setattr(
        "searchat.services.disk_accounting.get_connectors", lambda: ()
    )

    calls: list[dict] = []

    def fake_find_near_duplicates(db_path, *, connection=None, similarity_threshold=None):
        calls.append(
            {
                "db_path": db_path,
                "connection": connection,
                "similarity_threshold": similarity_threshold,
            }
        )
        return ()

    monkeypatch.setattr(
        "searchat.services.disk_accounting.find_near_duplicates", fake_find_near_duplicates
    )

    db_path = temp_search_dir / "data" / "missing.duckdb"
    config = Mock()
    config.storage.resolve_duckdb_path.return_value = db_path
    config.dedup.similarity_threshold = 0.85
    fake_connection = Mock(name="fake_duckdb_connection")
    fake_connection.cursor.return_value.execute.return_value.fetchall.return_value = []

    build_disk_accounting_report(temp_search_dir, config, connection=fake_connection)

    assert len(calls) == 1
    assert calls[0]["db_path"] == db_path
    assert calls[0]["connection"] is fake_connection
    assert calls[0]["similarity_threshold"] == 0.85


@pytest.mark.unit
def test_build_disk_accounting_report_resilient_when_find_near_duplicates_raises(
    temp_search_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """One bad subsystem (the dedup scan) never fails the whole report -- mirrors
    `test_build_disk_accounting_report_resilient_when_detect_cruft_raises`."""
    monkeypatch.setattr(
        "searchat.services.disk_accounting.get_connectors", lambda: ()
    )

    def _raise(*args, **kwargs):
        raise RuntimeError("dedup scan blew up")

    monkeypatch.setattr("searchat.services.disk_accounting.find_near_duplicates", _raise)

    config = Mock()
    config.storage.resolve_duckdb_path.return_value = (
        temp_search_dir / "data" / "missing.duckdb"
    )
    config.dedup.similarity_threshold = 0.92

    report = build_disk_accounting_report(temp_search_dir, config)

    assert report.duplicate_suggestions == ()


@pytest.mark.unit
def test_disk_accounting_report_duplicate_suggestions_defaults_to_empty_tuple() -> None:
    """Omitting `duplicate_suggestions` entirely keeps pre-M11 direct
    constructions working."""
    report = DiskAccountingReport(
        agents=(),
        searchat_self=SearchatSelfUsage(
            search_dir="/home/user/.searchat",
            subdirectories=(),
            total_size_bytes=0,
            total_file_count=0,
        ),
        generated_at="2026-07-03T12:00:00",
    )

    assert report.duplicate_suggestions == ()
    assert report.to_dict()["duplicate_suggestions"] == []
