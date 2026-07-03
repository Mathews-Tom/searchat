"""Tests for services/backup_scheduler.py (M10).

Covers the pure interval-gate decision function and BackupScheduler's
`run_once`, both exercised with an injected fixture clock (`now=`)
instead of real `time.sleep` -- mirroring
tests/unit/services/test_compaction.py's auto-trigger test shape.
"""
from __future__ import annotations

import json
import os
import time as time_module
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

import pytest

from searchat.services import backup_scheduler as sched
from searchat.services.backup import BackupManager
from searchat.services.storage_contracts import BackupMetadata


def _write_backup_metadata(mgr: BackupManager, *, name: str, timestamp: str) -> Path:
    """Author a backup_metadata.json directly, bypassing create_backup's
    real wall clock -- lets a test pin two backups to distinct,
    deterministic timestamps instead of racing the same second."""
    backup_path = mgr.backup_dir / name
    backup_path.mkdir(parents=True, exist_ok=True)
    metadata = BackupMetadata(
        timestamp=timestamp,
        backup_path=backup_path,
        source_path=mgr.data_dir,
        file_count=0,
        total_size_bytes=0,
        backup_type="manual",
    )
    (backup_path / mgr.METADATA_FILE).write_text(json.dumps(metadata.to_dict()))
    return backup_path


def _touch_source_file(temp_search_dir: Path, *, mtime: float) -> Path:
    """Write a source-of-truth file and pin its mtime -- simulates a
    data change at an exact instant, sidestepping filesystem mtime
    granularity/precision differences across platforms."""
    path = temp_search_dir / "data" / "conversations.parquet"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"PAR1")
    os.utime(path, (mtime, mtime))
    return path


@pytest.mark.unit
class TestShouldRunScheduledBackup:
    def test_no_prior_backup_always_fires(self) -> None:
        assert sched.should_run_scheduled_backup(last_backup_at=None, interval_hours=24.0) is True

    def test_recent_backup_does_not_fire(self) -> None:
        now = datetime(2026, 1, 8, 12, 0, 0, tzinfo=timezone.utc)
        recent = now - timedelta(hours=1)
        assert (
            sched.should_run_scheduled_backup(last_backup_at=recent, interval_hours=24.0, now=now)
            is False
        )

    def test_elapsed_backup_fires(self) -> None:
        now = datetime(2026, 1, 8, 12, 0, 0, tzinfo=timezone.utc)
        old = now - timedelta(hours=25)
        assert sched.should_run_scheduled_backup(last_backup_at=old, interval_hours=24.0, now=now) is True

    def test_exactly_at_interval_fires(self) -> None:
        now = datetime(2026, 1, 8, 12, 0, 0, tzinfo=timezone.utc)
        exact = now - timedelta(hours=24)
        assert (
            sched.should_run_scheduled_backup(last_backup_at=exact, interval_hours=24.0, now=now)
            is True
        )


@pytest.mark.unit
class TestParseBackupTimestamp:
    def test_matches_true_wall_clock_epoch_regardless_of_local_timezone(
        self, temp_search_dir: Path
    ) -> None:
        """Regression test: `_parse_backup_timestamp` must convert the
        naive-local timestamp to a true UTC instant, not merely relabel
        it -- otherwise every elapsed-time comparison against `now_fn`'s
        real UTC instants is skewed by the host's UTC offset (5.5h on a
        UTC+5:30 host, verified non-zero here to ensure this assertion
        cannot pass by coincidence on a UTC-local CI runner)."""
        mgr = BackupManager(temp_search_dir)
        before = time_module.time()
        meta = mgr.create_backup(backup_name="probe")
        after = time_module.time()

        parsed_epoch = sched._parse_backup_timestamp(meta).timestamp()

        assert before - 1 <= parsed_epoch <= after + 1


@pytest.mark.unit
class TestLastBackupMetadata:
    def test_no_backups_returns_none(self, temp_search_dir: Path) -> None:
        mgr = BackupManager(temp_search_dir)
        assert sched.last_backup_metadata(mgr) is None

    def test_returns_most_recent(self, temp_search_dir: Path) -> None:
        # Two independently-timestamped backups written directly (not via
        # create_backup, whose second-granularity timestamp could collide
        # between two real calls made microseconds apart) -- deterministic
        # coverage of list_backups()'s newest-first sort, matching the
        # tests/fixtures/storage/backup_contract_bundle convention of
        # authoring backup_metadata.json directly.
        mgr = BackupManager(temp_search_dir)
        _write_backup_metadata(mgr, name="one_20260101_000000", timestamp="20260101_000000")
        _write_backup_metadata(mgr, name="two_20260102_000000", timestamp="20260102_000000")

        result = sched.last_backup_metadata(mgr)

        assert result is not None
        assert result.timestamp == "20260102_000000"


@pytest.mark.unit
class TestBackupSchedulerRunOnce:
    def test_fires_when_no_prior_backup_exists(self, temp_search_dir: Path) -> None:
        mgr = BackupManager(temp_search_dir)
        scheduler = sched.BackupScheduler(manager=mgr, interval_hours=24.0)

        result = scheduler.run_once(now=datetime(2026, 1, 1, tzinfo=timezone.utc))

        assert result is not None
        assert result.backup_type == "scheduled"
        assert len(mgr.list_backups()) == 1

    def test_skips_when_interval_has_not_elapsed(self, temp_search_dir: Path) -> None:
        mgr = BackupManager(temp_search_dir)
        mgr.create_backup(backup_name="manual", backup_type="manual")
        scheduler = sched.BackupScheduler(manager=mgr, interval_hours=24.0)

        soon_after = datetime.now(timezone.utc) + timedelta(hours=1)
        with patch.object(mgr, "create_backup", wraps=mgr.create_backup) as spy:
            result = scheduler.run_once(now=soon_after)

        assert result is None
        spy.assert_not_called()

    def test_fires_at_the_configured_interval_fixture_time_advance(self, temp_search_dir: Path) -> None:
        mgr = BackupManager(temp_search_dir)
        mgr.create_backup(backup_name="manual", backup_type="manual")
        last = sched.last_backup_metadata(mgr)
        assert last is not None
        last_backup_at = sched._parse_backup_timestamp(last)
        _touch_source_file(temp_search_dir, mtime=last_backup_at.timestamp() + 1)

        scheduler = sched.BackupScheduler(manager=mgr, interval_hours=6.0)

        with patch.object(mgr, "create_backup", wraps=mgr.create_backup) as spy:
            # Advance the fixture clock hour-by-hour: no fire until 6h
            # have elapsed since the last backup's own recorded time.
            for hour in range(1, 6):
                result = scheduler.run_once(now=last_backup_at + timedelta(hours=hour))
                assert result is None, f"unexpected fire at +{hour}h"
            spy.assert_not_called()

            fired = scheduler.run_once(now=last_backup_at + timedelta(hours=6))

        assert fired is not None
        assert fired.backup_type == "scheduled"
        spy.assert_called_once_with(backup_type="scheduled")

    def test_run_once_uses_now_fn_when_now_not_passed(self, temp_search_dir: Path) -> None:
        mgr = BackupManager(temp_search_dir)
        mgr.create_backup(backup_name="manual", backup_type="manual")
        last = sched.last_backup_metadata(mgr)
        assert last is not None
        _touch_source_file(
            temp_search_dir, mtime=sched._parse_backup_timestamp(last).timestamp() + 1
        )

        # A fixture clock frozen well beyond the interval -- proves
        # run_once() falls back to now_fn() when `now=` is omitted.
        far_future = datetime.now(timezone.utc) + timedelta(days=365)
        scheduler = sched.BackupScheduler(
            manager=mgr, interval_hours=24.0, now_fn=lambda: far_future
        )

        result = scheduler.run_once()

        assert result is not None
        assert result.backup_type == "scheduled"


@pytest.mark.unit
class TestHasDataChangedSince:
    def test_no_source_files_is_unchanged(self, tmp_path: Path) -> None:
        assert sched.has_data_changed_since(tmp_path, datetime.now(timezone.utc)) is False

    def test_file_modified_after_since_is_changed(self, temp_search_dir: Path) -> None:
        since = datetime.now(timezone.utc) - timedelta(hours=1)
        _touch_source_file(temp_search_dir, mtime=since.timestamp() + 60)

        assert sched.has_data_changed_since(temp_search_dir, since) is True

    def test_file_modified_before_since_is_unchanged(self, temp_search_dir: Path) -> None:
        since = datetime.now(timezone.utc)
        _touch_source_file(temp_search_dir, mtime=since.timestamp() - 3600)

        assert sched.has_data_changed_since(temp_search_dir, since) is False

    def test_derived_indices_changes_are_ignored(self, temp_search_dir: Path) -> None:
        """`data/indices/` is the legacy FAISS/metadata index -- derived,
        never part of a backup, and irrelevant to source-of-truth change
        detection (mirrors BackupManager._iter_live_backup_files's own
        exclusion of this directory)."""
        since = datetime.now(timezone.utc)
        stale_source = temp_search_dir / "data" / "conversations.parquet"
        stale_source.parent.mkdir(parents=True, exist_ok=True)
        stale_source.write_bytes(b"PAR1")
        os.utime(stale_source, (since.timestamp() - 3600, since.timestamp() - 3600))

        fresh_derived = temp_search_dir / "data" / "indices" / "faiss.index"
        fresh_derived.parent.mkdir(parents=True, exist_ok=True)
        fresh_derived.write_bytes(b"IDX1")
        os.utime(fresh_derived, (since.timestamp() + 60, since.timestamp() + 60))

        assert sched.has_data_changed_since(temp_search_dir, since) is False


@pytest.mark.unit
class TestBackupSchedulerChangeDetectionGate:
    def test_second_scheduled_run_with_no_data_changes_is_skipped(
        self, temp_search_dir: Path
    ) -> None:
        """M10 acceptance: a second scheduled run, one full interval
        after the first, with no source-of-truth writes in between, is
        skipped -- and the backup engine's create function is never
        called for it."""
        mgr = BackupManager(temp_search_dir)
        scheduler = sched.BackupScheduler(manager=mgr, interval_hours=6.0)

        first = scheduler.run_once(now=datetime.now(timezone.utc))
        assert first is not None
        last_backup_at = sched._parse_backup_timestamp(first)

        with patch.object(mgr, "create_backup", wraps=mgr.create_backup) as spy:
            second = scheduler.run_once(now=last_backup_at + timedelta(hours=6))

        assert second is None
        spy.assert_not_called()

    def test_second_scheduled_run_fires_when_data_changed(self, temp_search_dir: Path) -> None:
        mgr = BackupManager(temp_search_dir)
        scheduler = sched.BackupScheduler(manager=mgr, interval_hours=6.0)

        first = scheduler.run_once(now=datetime.now(timezone.utc))
        assert first is not None
        last_backup_at = sched._parse_backup_timestamp(first)

        t1 = last_backup_at + timedelta(hours=6)
        _touch_source_file(temp_search_dir, mtime=t1.timestamp() - 60)

        with patch.object(mgr, "create_backup", wraps=mgr.create_backup) as spy:
            second = scheduler.run_once(now=t1)

        assert second is not None
        assert second.backup_type == "scheduled"
        spy.assert_called_once_with(backup_type="scheduled")
