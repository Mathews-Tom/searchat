"""Staleness scoring and pruning logic for the L2 expertise knowledge store."""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone

from searchat.config.settings import Config
from searchat.expertise.models import ExpertiseRecord, ExpertiseType
from searchat.expertise.store import ExpertiseStore


# Half-lives in days by expertise type
_HALF_LIVES: dict[ExpertiseType, float] = {
    ExpertiseType.BOUNDARY: 180.0,
    ExpertiseType.CONVENTION: 120.0,
    ExpertiseType.DECISION: 90.0,
    ExpertiseType.PATTERN: 90.0,
    ExpertiseType.FAILURE: 60.0,
    ExpertiseType.INSIGHT: 30.0,
}


def compute_staleness(record: ExpertiseRecord) -> float:
    """Compute staleness score from 0.0 (fresh) to 1.0 (stale).

    Formula: staleness = 1 - exp(-0.693 * days / adjusted_half_life)
    adjusted_hl = base_hl * (1 + min(validation_count, 10) * 0.1) * (0.8 + confidence * 0.4)
    """
    base_hl = _HALF_LIVES[record.type]
    adjusted_hl = (
        base_hl
        * (1.0 + min(record.validation_count, 10) * 0.1)
        * (0.8 + record.confidence * 0.4)
    )
    now = datetime.now(timezone.utc)
    last_validated = record.last_validated
    if last_validated.tzinfo is None:
        last_validated = last_validated.replace(tzinfo=timezone.utc)
    days = max((now - last_validated).total_seconds() / 86400.0, 0.0)
    return 1.0 - math.exp(-0.693 * days / adjusted_hl)


@dataclass
class PruneResult:
    pruned: list[ExpertiseRecord] = field(default_factory=list)
    skipped: list[ExpertiseRecord] = field(default_factory=list)
    total_evaluated: int = 0
    dry_run: bool = False


class StalenessManager:
    """Evaluate and prune stale expertise records."""

    def __init__(self, store: ExpertiseStore, config: Config) -> None:
        self._store = store
        self._config = config

    def compute_all_staleness(self) -> list[tuple[ExpertiseRecord, float]]:
        """Compute staleness scores for all active records."""
        # Use a far-future cutoff to fetch every active record
        far_future = datetime.now(timezone.utc) + timedelta(days=36500)
        records = self._store.get_stale_records(before=far_future)
        return [(r, compute_staleness(r)) for r in records]

    def get_stale_records(self, threshold: float = 0.85) -> list[tuple[ExpertiseRecord, float]]:
        """Return active records whose staleness score >= threshold."""
        return [
            (r, score)
            for r, score in self.compute_all_staleness()
            if score >= threshold
        ]

    def prune(
        self,
        threshold: float | None = None,
        dry_run: bool = False,
    ) -> PruneResult:
        """Soft-delete records that exceed the staleness threshold.

        Pruning rules from config:
        - staleness_threshold: deactivate records above this score
        - min_age_days: never prune records younger than this
        - min_validation_count: skip records validated >= this many times (0 = disabled)
        - exclude_types: never auto-prune these types
        """
        expertise_cfg = self._config.expertise
        effective_threshold = threshold if threshold is not None else expertise_cfg.staleness_threshold

        now = datetime.now(timezone.utc)
        min_created_before = now - timedelta(days=expertise_cfg.min_age_days)

        candidates = self.get_stale_records(threshold=effective_threshold)

        pruned: list[ExpertiseRecord] = []
        skipped: list[ExpertiseRecord] = []

        for record, _score in candidates:
            created_at = record.created_at
            if created_at.tzinfo is None:
                created_at = created_at.replace(tzinfo=timezone.utc)

            # Skip records younger than min_age_days
            if created_at > min_created_before:
                skipped.append(record)
                continue

            # Skip excluded types
            if record.type.value in expertise_cfg.exclude_types:
                skipped.append(record)
                continue

            # Skip records with enough validations (0 = disabled)
            if (
                expertise_cfg.min_validation_count > 0
                and record.validation_count >= expertise_cfg.min_validation_count
            ):
                skipped.append(record)
                continue

            pruned.append(record)

        if not dry_run and pruned:
            self._store.bulk_soft_delete([r.id for r in pruned])

        return PruneResult(
            pruned=pruned,
            skipped=skipped,
            total_evaluated=len(candidates),
            dry_run=dry_run,
        )
