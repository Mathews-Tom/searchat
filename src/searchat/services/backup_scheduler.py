"""Scheduled backups (M10) -- a cron-style interval trigger over M4's
backup engine (`services/backup.py::BackupManager`), reused unchanged.

Mirrors `services/compaction.py`'s auto-trigger shape: a pure decision
function (`should_run_scheduled_backup`) takes an explicit `now`, so the
interval gate is testable with a fixture clock instead of real
`time.sleep` -- no time-mocking dependency needed. A second gate,
`has_data_changed_since`, skips a run when no source-of-truth file has
been touched since the last backup, so an idle dataset doesn't
accumulate no-op backups every interval. `BackupScheduler` wraps both
decision functions around `BackupManager.list_backups` and
`BackupManager.create_backup`, both used exactly as M4 shipped them;
this module contributes no changes to backup content or retention
logic, only the trigger that decides *when* to call `create_backup`.
"""
from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

from searchat.config.constants import DEFAULT_DATA_SUBDIR
from searchat.services.backup import BackupManager
from searchat.services.storage_contracts import BackupMetadata

logger = logging.getLogger(__name__)

# Matches BackupManager.create_backup's `datetime.now().strftime(...)`.
_BACKUP_TIMESTAMP_FORMAT = "%Y%m%d_%H%M%S"


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _parse_backup_timestamp(metadata: BackupMetadata) -> datetime:
    """Parse `BackupMetadata.timestamp` into a true UTC-aware instant.

    The timestamp is naive *local* time (`BackupManager.create_backup`'s
    `datetime.now().strftime(...)`). `astimezone(timezone.utc)` on a
    naive datetime is interpreted by the standard library as system
    local time and converted correctly -- unlike `.replace(tzinfo=utc)`,
    which would mislabel it and skew every elapsed-time comparison
    against `now_fn`'s true UTC instants by the host's UTC offset.
    """
    naive_local = datetime.strptime(metadata.timestamp, _BACKUP_TIMESTAMP_FORMAT)
    return naive_local.astimezone(timezone.utc)


def last_backup_metadata(manager: BackupManager) -> BackupMetadata | None:
    """Most recent backup of any type (manual, scheduled, pre_restore).

    Any prior backup protects the same data, so any of them resets the
    scheduling clock -- a manual backup taken five minutes ago should
    postpone the next scheduled run just as a scheduled one would.
    """
    backups = manager.list_backups()
    return backups[0] if backups else None


def should_run_scheduled_backup(
    *,
    last_backup_at: datetime | None,
    interval_hours: float,
    now: datetime | None = None,
) -> bool:
    """Pure decision function: fire only once at least `interval_hours`
    have elapsed since the last backup. No prior backup always fires."""
    if last_backup_at is None:
        return True
    elapsed_hours = ((now or _utc_now()) - last_backup_at).total_seconds() / 3600
    return elapsed_hours >= interval_hours


# Source-of-truth items a scheduled run checks for changes -- the same
# top-level scope BackupManager._iter_live_backup_files(excludes_derived=True)
# backs up (data/, config/, bookmarks.json, saved_queries.json,
# dashboards.json, expertise/, knowledge_graph/, analytics/), except
# that method deliberately EXCLUDES `data/searchat.duckdb` itself (its
# source-of-truth tables are exported to fresh Parquet on every backup
# instead of being copied verbatim -- see that method's docstring), so
# the exported files' own mtimes are always "now" and useless for
# diffing. The live database file's mtime is instead the correct,
# cheap-to-stat proxy for "did the underlying data change" without
# re-running that export. `data/indices/` (the derivable FAISS/metadata
# index) is excluded, matching the backup's own scope -- it is never
# protected by a backup and is irrelevant to source-of-truth change
# detection.
_SOURCE_TREE_ITEMS: tuple[str, ...] = (
    DEFAULT_DATA_SUBDIR,
    "config",
    "bookmarks.json",
    "saved_queries.json",
    "dashboards.json",
    "expertise",
    "knowledge_graph",
    "analytics",
)


def _latest_source_mtime(data_dir: Path) -> float | None:
    """Latest mtime (epoch seconds) across every source-of-truth file
    under `data_dir`. Returns `None` when nothing exists yet."""
    skip_dir = (data_dir / DEFAULT_DATA_SUBDIR / "indices").resolve()
    latest: float | None = None
    for name in _SOURCE_TREE_ITEMS:
        root = data_dir / name
        if not root.exists():
            continue
        paths = [root] if root.is_file() else [p for p in root.rglob("*") if p.is_file()]
        for path in paths:
            if skip_dir in path.resolve().parents:
                continue
            mtime = path.stat().st_mtime
            if latest is None or mtime > latest:
                latest = mtime
    return latest


def has_data_changed_since(data_dir: Path, since: datetime) -> bool:
    """True if any source-of-truth file under `data_dir` was modified
    after `since` (typically the last backup's own creation time).

    A dataset with no source files at all (nothing indexed yet) counts
    as unchanged -- there is nothing new to protect, so a scheduled run
    should skip rather than create an empty backup.
    """
    latest = _latest_source_mtime(Path(data_dir))
    if latest is None:
        return False
    return latest > since.timestamp()


@dataclass
class BackupScheduler:
    """Cron-style interval trigger invoking M4's `BackupManager.create_backup`.

    `now_fn` is injectable for tests; production callers use the default
    (`datetime.now(timezone.utc)`).
    """

    manager: BackupManager
    interval_hours: float
    now_fn: Callable[[], datetime] = _utc_now

    def run_once(self, *, now: datetime | None = None) -> BackupMetadata | None:
        """Create a scheduled backup if the interval has elapsed AND the
        source-of-truth data has actually changed since the last backup.

        Returns the new backup's metadata, or `None` when skipped.
        """
        effective_now = now if now is not None else self.now_fn()
        last = last_backup_metadata(self.manager)
        last_backup_at = _parse_backup_timestamp(last) if last is not None else None

        if not should_run_scheduled_backup(
            last_backup_at=last_backup_at,
            interval_hours=self.interval_hours,
            now=effective_now,
        ):
            logger.debug(
                "Scheduled backup skipped: interval not yet elapsed (last backup: %s)",
                last_backup_at or "never",
            )
            return None

        if last_backup_at is not None and not has_data_changed_since(
            self.manager.data_dir, last_backup_at
        ):
            logger.info(
                "Scheduled backup skipped: no data changed since last backup (%s)",
                last.timestamp if last is not None else "never",
            )
            return None

        logger.info(
            "Scheduled backup triggered (interval: %.2fh, last backup: %s)",
            self.interval_hours,
            last_backup_at or "never",
        )
        return self.manager.create_backup(backup_type="scheduled")

    def run_forever(self, *, poll_seconds: float = 300.0) -> None:
        """Blocking loop for production use.

        Checks the interval gate every `poll_seconds`, letting
        `run_once` decide whether a backup actually fires -- mirrors
        `daemon/ghost.py::GhostDaemon.run_forever`'s poll-then-decide
        shape. Not exercised by tests; those call `run_once` directly
        with a fixture clock.
        """
        while True:
            self.run_once()
            time.sleep(max(1.0, poll_seconds))
