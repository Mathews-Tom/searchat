"""Tests for staleness scoring and pruning logic."""
from __future__ import annotations

import math
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from searchat.config.settings import Config, ExpertiseConfig
from searchat.expertise.models import ExpertiseRecord, ExpertiseType
from searchat.expertise.staleness import PruneResult, StalenessManager, compute_staleness
from searchat.expertise.store import ExpertiseStore


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _record(
    *,
    type: ExpertiseType = ExpertiseType.CONVENTION,
    domain: str = "test",
    content: str = "content",
    confidence: float = 1.0,
    validation_count: int = 1,
    last_validated: datetime | None = None,
    created_at: datetime | None = None,
    **kwargs,
) -> ExpertiseRecord:
    now = _utcnow()
    return ExpertiseRecord(
        type=type,
        domain=domain,
        content=content,
        confidence=confidence,
        validation_count=validation_count,
        last_validated=last_validated if last_validated is not None else now,
        created_at=created_at if created_at is not None else now,
        **kwargs,
    )


def _expertise_config(
    staleness_threshold: float = 0.85,
    min_age_days: int = 30,
    min_validation_count: int = 0,
    exclude_types: list[str] | None = None,
    pruning_enabled: bool = True,
    pruning_dry_run: bool = False,
) -> ExpertiseConfig:
    return ExpertiseConfig(
        enabled=True,
        auto_extract=False,
        default_prime_tokens=4000,
        dedup_similarity_threshold=0.95,
        dedup_flag_threshold=0.80,
        staleness_threshold=staleness_threshold,
        min_age_days=min_age_days,
        min_validation_count=min_validation_count,
        exclude_types=exclude_types if exclude_types is not None else ["boundary"],
        pruning_enabled=pruning_enabled,
        pruning_dry_run=pruning_dry_run,
    )


def _config(expertise: ExpertiseConfig | None = None) -> MagicMock:
    cfg = MagicMock(spec=Config)
    cfg.expertise = expertise if expertise is not None else _expertise_config()
    return cfg


@pytest.fixture
def store(tmp_path: Path) -> ExpertiseStore:
    return ExpertiseStore(data_dir=tmp_path)


# ---------------------------------------------------------------------------
# compute_staleness unit tests
# ---------------------------------------------------------------------------

class TestComputeStaleness:
    def test_just_validated_is_near_zero(self) -> None:
        rec = _record(last_validated=_utcnow())
        score = compute_staleness(rec)
        assert score < 0.01

    def test_very_old_insight_approaches_one(self) -> None:
        old = _utcnow() - timedelta(days=365)
        rec = _record(type=ExpertiseType.INSIGHT, last_validated=old)
        score = compute_staleness(rec)
        assert score > 0.99

    def test_boundary_decays_slower_than_insight(self) -> None:
        validated_90_days_ago = _utcnow() - timedelta(days=90)
        boundary = _record(type=ExpertiseType.BOUNDARY, last_validated=validated_90_days_ago)
        insight = _record(type=ExpertiseType.INSIGHT, last_validated=validated_90_days_ago)
        assert compute_staleness(boundary) < compute_staleness(insight)

    def test_higher_validation_count_extends_half_life(self) -> None:
        validated = _utcnow() - timedelta(days=60)
        low_val = _record(type=ExpertiseType.FAILURE, last_validated=validated, validation_count=1)
        high_val = _record(type=ExpertiseType.FAILURE, last_validated=validated, validation_count=10)
        assert compute_staleness(low_val) > compute_staleness(high_val)

    def test_higher_confidence_extends_half_life(self) -> None:
        validated = _utcnow() - timedelta(days=60)
        low_conf = _record(type=ExpertiseType.PATTERN, last_validated=validated, confidence=0.0)
        high_conf = _record(type=ExpertiseType.PATTERN, last_validated=validated, confidence=1.0)
        assert compute_staleness(low_conf) > compute_staleness(high_conf)

    def test_score_between_zero_and_one(self) -> None:
        for days in [0, 30, 90, 365]:
            validated = _utcnow() - timedelta(days=days)
            for t in ExpertiseType:
                rec = _record(type=t, last_validated=validated)
                score = compute_staleness(rec)
                assert 0.0 <= score <= 1.0, f"score={score} for type={t}, days={days}"

    def test_half_life_approximation(self) -> None:
        # At exactly one half-life (with default adjustments), score ~= 0.5
        # With validation_count=1, confidence=1.0:
        # adjusted_hl = 30 * (1 + 0.1) * (0.8 + 0.4) = 30 * 1.1 * 1.2 = 39.6
        adjusted_hl = 30 * (1 + 1 * 0.1) * (0.8 + 1.0 * 0.4)
        validated = _utcnow() - timedelta(days=adjusted_hl)
        rec = _record(type=ExpertiseType.INSIGHT, last_validated=validated, validation_count=1, confidence=1.0)
        score = compute_staleness(rec)
        assert abs(score - 0.5) < 0.01

    def test_naive_datetime_treated_as_utc(self) -> None:
        # Should not raise; naive datetime treated as UTC
        naive = datetime.now()  # naive
        rec = _record(last_validated=naive)
        score = compute_staleness(rec)
        assert 0.0 <= score <= 1.0


# ---------------------------------------------------------------------------
# store.get_stale_records and store.bulk_soft_delete tests
# ---------------------------------------------------------------------------

class TestStoreStaleRecords:
    def test_get_stale_records_returns_correct_records(self, store: ExpertiseStore) -> None:
        cutoff = _utcnow()
        old_validated = cutoff - timedelta(days=90)
        new_validated = cutoff + timedelta(days=1)

        old_rec = _record(last_validated=old_validated)
        new_rec = _record(last_validated=new_validated)

        store.insert(old_rec)
        store.insert(new_rec)

        stale = store.get_stale_records(before=cutoff)
        ids = {r.id for r in stale}

        assert old_rec.id in ids
        assert new_rec.id not in ids

    def test_get_stale_records_excludes_inactive(self, store: ExpertiseStore) -> None:
        old_validated = _utcnow() - timedelta(days=90)
        rec = _record(last_validated=old_validated)
        store.insert(rec)
        store.soft_delete(rec.id)

        stale = store.get_stale_records(before=_utcnow())
        assert not any(r.id == rec.id for r in stale)

    def test_bulk_soft_delete_returns_count(self, store: ExpertiseStore) -> None:
        recs = [_record() for _ in range(3)]
        for r in recs:
            store.insert(r)

        ids = [r.id for r in recs]
        deleted = store.bulk_soft_delete(ids)
        assert deleted == 3

        for r in recs:
            fetched = store.get(r.id)
            assert fetched is not None
            assert fetched.is_active is False

    def test_bulk_soft_delete_empty_list_returns_zero(self, store: ExpertiseStore) -> None:
        assert store.bulk_soft_delete([]) == 0

    def test_bulk_soft_delete_ignores_unknown_ids(self, store: ExpertiseStore) -> None:
        count = store.bulk_soft_delete(["nonexistent-id"])
        assert count == 0


# ---------------------------------------------------------------------------
# StalenessManager tests
# ---------------------------------------------------------------------------

class TestStalenessManager:
    def test_get_stale_records_filters_by_threshold(self, store: ExpertiseStore) -> None:
        # Insert one very old insight (high staleness) and one fresh record
        old = _record(type=ExpertiseType.INSIGHT, last_validated=_utcnow() - timedelta(days=365))
        fresh = _record(type=ExpertiseType.BOUNDARY, last_validated=_utcnow())
        store.insert(old)
        store.insert(fresh)

        manager = StalenessManager(store=store, config=_config())
        stale = manager.get_stale_records(threshold=0.85)
        ids = {r.id for r, _ in stale}

        assert old.id in ids
        assert fresh.id not in ids

    def test_prune_respects_min_age_days(self, store: ExpertiseStore) -> None:
        # Record is stale but younger than min_age_days
        rec = _record(
            type=ExpertiseType.INSIGHT,
            last_validated=_utcnow() - timedelta(days=365),
            created_at=_utcnow() - timedelta(days=10),  # only 10 days old
        )
        store.insert(rec)

        cfg = _config(_expertise_config(min_age_days=30))
        manager = StalenessManager(store=store, config=cfg)
        result = manager.prune(threshold=0.0)

        assert rec.id not in {r.id for r in result.pruned}
        assert rec.id in {r.id for r in result.skipped}
        fetched = store.get(rec.id)
        assert fetched is not None and fetched.is_active is True

    def test_prune_respects_exclude_types(self, store: ExpertiseStore) -> None:
        old = _utcnow() - timedelta(days=365)
        rec = _record(
            type=ExpertiseType.BOUNDARY,
            last_validated=old,
            created_at=old,
        )
        store.insert(rec)

        cfg = _config(_expertise_config(exclude_types=["boundary"]))
        manager = StalenessManager(store=store, config=cfg)
        result = manager.prune(threshold=0.0)

        assert rec.id in {r.id for r in result.skipped}
        assert rec.id not in {r.id for r in result.pruned}
        fetched = store.get(rec.id)
        assert fetched is not None and fetched.is_active is True

    def test_prune_respects_min_validation_count(self, store: ExpertiseStore) -> None:
        old = _utcnow() - timedelta(days=365)
        rec = _record(
            type=ExpertiseType.INSIGHT,
            last_validated=old,
            created_at=old,
            validation_count=5,
        )
        store.insert(rec)

        cfg = _config(_expertise_config(min_validation_count=5))
        manager = StalenessManager(store=store, config=cfg)
        result = manager.prune(threshold=0.0)

        assert rec.id in {r.id for r in result.skipped}
        assert rec.id not in {r.id for r in result.pruned}

    def test_prune_dry_run_does_not_delete(self, store: ExpertiseStore) -> None:
        old = _utcnow() - timedelta(days=365)
        rec = _record(
            type=ExpertiseType.INSIGHT,
            last_validated=old,
            created_at=old,
        )
        store.insert(rec)

        cfg = _config(_expertise_config())
        manager = StalenessManager(store=store, config=cfg)
        result = manager.prune(threshold=0.0, dry_run=True)

        assert result.dry_run is True
        assert rec.id in {r.id for r in result.pruned}
        # Record must still be active
        fetched = store.get(rec.id)
        assert fetched is not None and fetched.is_active is True

    def test_prune_deletes_qualifying_records(self, store: ExpertiseStore) -> None:
        old = _utcnow() - timedelta(days=365)
        rec = _record(
            type=ExpertiseType.INSIGHT,
            last_validated=old,
            created_at=old,
        )
        store.insert(rec)

        cfg = _config(_expertise_config(exclude_types=[]))
        manager = StalenessManager(store=store, config=cfg)
        result = manager.prune(threshold=0.0, dry_run=False)

        assert rec.id in {r.id for r in result.pruned}
        fetched = store.get(rec.id)
        assert fetched is not None and fetched.is_active is False

    def test_prune_result_total_evaluated(self, store: ExpertiseStore) -> None:
        old = _utcnow() - timedelta(days=365)
        for _ in range(3):
            rec = _record(type=ExpertiseType.INSIGHT, last_validated=old, created_at=old)
            store.insert(rec)

        cfg = _config(_expertise_config(exclude_types=[]))
        manager = StalenessManager(store=store, config=cfg)
        result = manager.prune(threshold=0.0)

        assert result.total_evaluated == 3

    def test_compute_all_staleness_covers_all_active(self, store: ExpertiseStore) -> None:
        recs = [
            _record(type=ExpertiseType.INSIGHT, last_validated=_utcnow() - timedelta(days=i * 30))
            for i in range(4)
        ]
        for r in recs:
            store.insert(r)

        # Deactivate one
        store.soft_delete(recs[0].id)

        manager = StalenessManager(store=store, config=_config())
        scored = manager.compute_all_staleness()
        ids = {r.id for r, _ in scored}

        # Active records returned
        for r in recs[1:]:
            assert r.id in ids
        # Inactive excluded
        assert recs[0].id not in ids
