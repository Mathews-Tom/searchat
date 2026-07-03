"""Scheduled backups (M10) -- a cron-style interval trigger over M4's
backup engine (`services/backup.py::BackupManager`), reused unchanged.

Mirrors `services/compaction.py`'s auto-trigger shape: a pure decision
function (`should_run_scheduled_backup`) takes an explicit `now`, so the
interval gate is testable with a fixture clock instead of real
`time.sleep` -- no time-mocking dependency needed. `BackupScheduler`
wraps that decision function around `BackupManager.list_backups` and
`BackupManager.create_backup`, both used exactly as M4 shipped them;
this module contributes no changes to backup content or retention
logic, only the trigger that decides *when* to call `create_backup`.
"""
from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Callable

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
        """Create a scheduled backup if the interval has elapsed.

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
