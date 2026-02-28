"""API tests for expertise staleness, prune, and domain patch endpoints."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from searchat.api.app import app
from searchat.expertise.models import ExpertiseRecord, ExpertiseType


@pytest.fixture
def client():
    return TestClient(app)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _make_record(
    type: ExpertiseType = ExpertiseType.CONVENTION,
    domain: str = "testing",
    content: str = "test content",
    **kwargs,
) -> ExpertiseRecord:
    return ExpertiseRecord(type=type, domain=domain, content=content, **kwargs)


def _make_old_record(domain: str = "testing", **kwargs) -> ExpertiseRecord:
    """Record with last_validated 200 days ago (guaranteed stale for INSIGHT type)."""
    old_date = _utcnow() - timedelta(days=200)
    return ExpertiseRecord(
        type=ExpertiseType.INSIGHT,
        domain=domain,
        content="old insight",
        last_validated=old_date,
        created_at=old_date - timedelta(days=10),
        **kwargs,
    )


def _mock_config(
    prime_tokens: int = 4000,
    staleness_threshold: float = 0.85,
    min_age_days: int = 30,
    min_validation_count: int = 0,
    exclude_types: list[str] | None = None,
    pruning_enabled: bool = True,
    pruning_dry_run: bool = False,
):
    return SimpleNamespace(
        expertise=SimpleNamespace(
            enabled=True,
            default_prime_tokens=prime_tokens,
            staleness_threshold=staleness_threshold,
            min_age_days=min_age_days,
            min_validation_count=min_validation_count,
            exclude_types=exclude_types or ["boundary"],
            pruning_enabled=pruning_enabled,
            pruning_dry_run=pruning_dry_run,
        )
    )


@pytest.fixture
def mock_store():
    return MagicMock()


@pytest.fixture
def patched_store(mock_store):
    with patch("searchat.api.routers.expertise.get_expertise_store", return_value=mock_store):
        with patch("searchat.api.routers.expertise.get_config", return_value=_mock_config()):
            yield mock_store


class TestGetStaleRecords:
    def test_get_stale_records_empty_store(self, client, patched_store):
        patched_store.get_stale_records.return_value = []

        resp = client.get("/api/expertise/stale")

        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 0
        assert data["results"] == []
        assert data["threshold"] == 0.85

    def test_get_stale_records_with_threshold(self, client, patched_store):
        old_record = _make_old_record()
        patched_store.get_stale_records.return_value = [old_record]

        resp = client.get("/api/expertise/stale?threshold=0.5")

        assert resp.status_code == 200
        data = resp.json()
        assert data["threshold"] == 0.5

    def test_get_stale_records_filters_by_domain(self, client, patched_store):
        rec_a = _make_old_record(domain="auth")
        rec_b = _make_old_record(domain="db")
        patched_store.get_stale_records.return_value = [rec_a, rec_b]

        resp = client.get("/api/expertise/stale?domain=auth&threshold=0.0")

        assert resp.status_code == 200
        data = resp.json()
        for item in data["results"]:
            assert item["record"]["domain"] == "auth"

    def test_get_stale_records_sorted_by_staleness_descending(self, client, patched_store):
        # Two records with different ages; older = more stale
        recent_record = _make_record(
            type=ExpertiseType.INSIGHT,
            last_validated=_utcnow() - timedelta(days=10),
        )
        old_record = _make_old_record()
        patched_store.get_stale_records.return_value = [recent_record, old_record]

        resp = client.get("/api/expertise/stale?threshold=0.0")

        assert resp.status_code == 200
        data = resp.json()
        scores = [item["staleness_score"] for item in data["results"]]
        assert scores == sorted(scores, reverse=True)


class TestPruneEndpoint:
    def test_prune_dry_run_default(self, client, patched_store):
        """Default body has dry_run=True."""
        from searchat.expertise.staleness import PruneResult

        patched_store.get_stale_records.return_value = []
        mock_result = PruneResult(pruned=[], skipped=[], total_evaluated=0, dry_run=True)

        with patch("searchat.api.routers.expertise.StalenessManager") as MockManager:
            instance = MockManager.return_value
            instance.prune.return_value = mock_result

            resp = client.post("/api/expertise/prune", json={})

        assert resp.status_code == 200
        data = resp.json()
        assert data["dry_run"] is True
        assert data["pruned_count"] == 0

    def test_prune_dry_run_does_not_delete(self, client, patched_store):
        old_rec = _make_old_record()
        from searchat.expertise.staleness import PruneResult

        mock_result = PruneResult(pruned=[], skipped=[old_rec], total_evaluated=1, dry_run=True)

        with patch("searchat.api.routers.expertise.StalenessManager") as MockManager:
            instance = MockManager.return_value
            instance.prune.return_value = mock_result

            resp = client.post("/api/expertise/prune", json={"dry_run": True})

        assert resp.status_code == 200
        data = resp.json()
        assert data["dry_run"] is True
        patched_store.bulk_soft_delete.assert_not_called()

    def test_prune_with_force(self, client, patched_store):
        old_rec = _make_old_record()
        from searchat.expertise.staleness import PruneResult

        mock_result = PruneResult(
            pruned=[old_rec], skipped=[], total_evaluated=1, dry_run=False
        )

        with patch("searchat.api.routers.expertise.StalenessManager") as MockManager:
            instance = MockManager.return_value
            instance.prune.return_value = mock_result

            resp = client.post("/api/expertise/prune", json={"dry_run": False})

        assert resp.status_code == 200
        data = resp.json()
        assert data["dry_run"] is False
        assert data["pruned_count"] == 1
        assert old_rec.id in data["pruned_ids"]

    def test_prune_custom_threshold(self, client, patched_store):
        from searchat.expertise.staleness import PruneResult

        mock_result = PruneResult(pruned=[], skipped=[], total_evaluated=0, dry_run=True)

        with patch("searchat.api.routers.expertise.StalenessManager") as MockManager:
            instance = MockManager.return_value
            instance.prune.return_value = mock_result

            resp = client.post("/api/expertise/prune", json={"threshold": 0.5, "dry_run": True})

        assert resp.status_code == 200
        call_kwargs = instance.prune.call_args.kwargs
        assert call_kwargs["threshold"] == 0.5


class TestPatchDomain:
    def test_patch_domain_rename(self, client, patched_store):
        patched_store.list_domains.return_value = [
            {
                "name": "new-name",
                "description": "desc",
                "record_count": 5,
                "last_updated": _utcnow().isoformat(),
            }
        ]
        mock_con = MagicMock()
        mock_con.__enter__ = MagicMock(return_value=mock_con)
        mock_con.__exit__ = MagicMock(return_value=False)
        patched_store._connect.return_value = mock_con

        resp = client.patch("/api/expertise/domains/old-name", json={"new_name": "new-name"})

        assert resp.status_code == 200
        data = resp.json()
        assert data["name"] == "new-name"

    def test_patch_domain_merge(self, client, patched_store):
        old_rec = _make_record(domain="src-domain")
        patched_store.query.return_value = [old_rec]
        patched_store.list_domains.return_value = [
            {
                "name": "target-domain",
                "description": "desc",
                "record_count": 3,
                "last_updated": _utcnow().isoformat(),
            }
        ]
        mock_con = MagicMock()
        patched_store._connect.return_value = mock_con

        resp = client.patch(
            "/api/expertise/domains/src-domain",
            json={"merge_into": "target-domain"},
        )

        assert resp.status_code == 200
        data = resp.json()
        assert data["name"] == "target-domain"
        patched_store.update.assert_called_once_with(old_rec.id, domain="target-domain")


class TestEnhancedStatus:
    def test_enhanced_status_includes_health(self, client, patched_store):
        fresh_record = _make_record(
            domain="coding",
            is_active=True,
            last_validated=_utcnow(),
        )
        patched_store.query.return_value = [fresh_record]
        patched_store.get_domain_stats.return_value = {
            "domain": "coding",
            "total_records": 1,
            "active_records": 1,
        }

        resp = client.get("/api/expertise/status")

        assert resp.status_code == 200
        data = resp.json()
        assert "domains" in data
        assert len(data["domains"]) == 1
        domain_stat = data["domains"][0]
        assert "stale_count" in domain_stat
        assert "health" in domain_stat
        assert "stalest_record_days" in domain_stat
        assert domain_stat["health"] in ("healthy", "warning", "critical")

    def test_enhanced_status_healthy_domain(self, client, patched_store):
        fresh = _make_record(domain="coding", is_active=True, last_validated=_utcnow())
        patched_store.query.return_value = [fresh]
        patched_store.get_domain_stats.return_value = {
            "domain": "coding",
            "total_records": 1,
            "active_records": 1,
        }

        resp = client.get("/api/expertise/status")

        assert resp.status_code == 200
        data = resp.json()
        assert data["domains"][0]["health"] == "healthy"
        assert data["domains"][0]["stale_count"] == 0

    def test_enhanced_status_critical_domain(self, client, patched_store):
        old1 = _make_old_record(domain="auth")
        old2 = _make_old_record(domain="auth")
        old1.is_active = True
        old2.is_active = True
        patched_store.query.return_value = [old1, old2]
        patched_store.get_domain_stats.return_value = {
            "domain": "auth",
            "total_records": 2,
            "active_records": 2,
        }

        resp = client.get("/api/expertise/status")

        assert resp.status_code == 200
        data = resp.json()
        # Both are old INSIGHT records — should be stale
        assert data["domains"][0]["stale_count"] >= 1
