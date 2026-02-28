"""Tests for ExpertiseStore DuckDB backend."""
from __future__ import annotations

import time
from pathlib import Path

import pytest

from searchat.expertise.models import (
    ExpertiseQuery,
    ExpertiseRecord,
    ExpertiseSeverity,
    ExpertiseType,
)
from searchat.expertise.store import ExpertiseStore


@pytest.fixture
def expertise_store(tmp_path: Path) -> ExpertiseStore:
    return ExpertiseStore(data_dir=tmp_path)


def _make_record(
    *,
    type: ExpertiseType = ExpertiseType.CONVENTION,
    domain: str = "test-domain",
    content: str = "some content",
    **kwargs,
) -> ExpertiseRecord:
    return ExpertiseRecord(type=type, domain=domain, content=content, **kwargs)


class TestTableCreation:
    def test_tables_created(self, expertise_store: ExpertiseStore, tmp_path: Path) -> None:
        import duckdb

        db_path = tmp_path / "expertise" / "expertise.duckdb"
        assert db_path.exists()

        con = duckdb.connect(database=str(db_path))
        try:
            tables = {row[0] for row in con.execute("SHOW TABLES").fetchall()}
        finally:
            con.close()

        assert "expertise_records" in tables
        assert "expertise_domains" in tables


class TestInsertAndGet:
    def test_insert_returns_id(self, expertise_store: ExpertiseStore) -> None:
        rec = _make_record()
        result_id = expertise_store.insert(rec)
        assert result_id == rec.id

    def test_get_by_id(self, expertise_store: ExpertiseStore) -> None:
        rec = _make_record(
            type=ExpertiseType.DECISION,
            domain="architecture",
            content="Use hexagonal architecture",
            project="my-app",
            confidence=0.9,
            tags=["arch", "pattern"],
            severity=ExpertiseSeverity.HIGH,
            name="HexArch",
            rationale="Better testability",
            alternatives_considered=["layered", "MVC"],
            source_agent="claude-opus-4-6",
            source_conversation_id="conv-001",
        )
        expertise_store.insert(rec)
        fetched = expertise_store.get(rec.id)

        assert fetched is not None
        assert fetched.id == rec.id
        assert fetched.type == ExpertiseType.DECISION
        assert fetched.domain == "architecture"
        assert fetched.content == "Use hexagonal architecture"
        assert fetched.project == "my-app"
        assert abs(fetched.confidence - 0.9) < 1e-9
        assert fetched.tags == ["arch", "pattern"]
        assert fetched.severity == ExpertiseSeverity.HIGH
        assert fetched.name == "HexArch"
        assert fetched.rationale == "Better testability"
        assert fetched.alternatives_considered == ["layered", "MVC"]
        assert fetched.source_agent == "claude-opus-4-6"
        assert fetched.source_conversation_id == "conv-001"
        assert fetched.is_active is True
        assert fetched.validation_count == 1

    def test_get_nonexistent_returns_none(self, expertise_store: ExpertiseStore) -> None:
        assert expertise_store.get("exp_doesnotexist") is None


class TestInsertAllTypes:
    def test_insert_all_expertise_types(self, expertise_store: ExpertiseStore) -> None:
        for etype in ExpertiseType:
            rec = _make_record(type=etype, content=f"content for {etype.value}")
            expertise_store.insert(rec)
            fetched = expertise_store.get(rec.id)
            assert fetched is not None
            assert fetched.type == etype


class TestSoftDelete:
    def test_soft_delete_sets_inactive(self, expertise_store: ExpertiseStore) -> None:
        rec = _make_record()
        expertise_store.insert(rec)
        expertise_store.soft_delete(rec.id)

        fetched = expertise_store.get(rec.id)
        assert fetched is not None
        assert fetched.is_active is False

    def test_soft_delete_nonexistent_does_not_raise(self, expertise_store: ExpertiseStore) -> None:
        # DuckDB rowcount is always -1; operation completes without error
        expertise_store.soft_delete("exp_doesnotexist")


class TestQueryByDomain:
    def test_filter_by_domain(self, expertise_store: ExpertiseStore) -> None:
        rec_a = _make_record(domain="python", content="use type hints")
        rec_b = _make_record(domain="rust", content="use ownership")
        expertise_store.insert(rec_a)
        expertise_store.insert(rec_b)

        results = expertise_store.query(ExpertiseQuery(domain="python"))
        ids = {r.id for r in results}
        assert rec_a.id in ids
        assert rec_b.id not in ids


class TestQueryByType:
    def test_filter_by_type(self, expertise_store: ExpertiseStore) -> None:
        convention = _make_record(type=ExpertiseType.CONVENTION)
        pattern = _make_record(type=ExpertiseType.PATTERN)
        expertise_store.insert(convention)
        expertise_store.insert(pattern)

        results = expertise_store.query(ExpertiseQuery(type=ExpertiseType.PATTERN))
        ids = {r.id for r in results}
        assert pattern.id in ids
        assert convention.id not in ids


class TestQueryByProject:
    def test_filter_by_project(self, expertise_store: ExpertiseStore) -> None:
        rec_proj_a = _make_record(project="alpha", content="alpha content")
        rec_proj_b = _make_record(project="beta", content="beta content")
        rec_no_proj = _make_record(project=None, content="no project content")
        expertise_store.insert(rec_proj_a)
        expertise_store.insert(rec_proj_b)
        expertise_store.insert(rec_no_proj)

        results = expertise_store.query(ExpertiseQuery(project="alpha"))
        ids = {r.id for r in results}
        assert rec_proj_a.id in ids
        assert rec_proj_b.id not in ids
        assert rec_no_proj.id not in ids


class TestQueryCombinedFilters:
    def test_domain_and_type(self, expertise_store: ExpertiseStore) -> None:
        match = _make_record(domain="api", type=ExpertiseType.FAILURE)
        wrong_domain = _make_record(domain="db", type=ExpertiseType.FAILURE)
        wrong_type = _make_record(domain="api", type=ExpertiseType.PATTERN)
        for rec in (match, wrong_domain, wrong_type):
            expertise_store.insert(rec)

        results = expertise_store.query(
            ExpertiseQuery(domain="api", type=ExpertiseType.FAILURE)
        )
        ids = {r.id for r in results}
        assert match.id in ids
        assert wrong_domain.id not in ids
        assert wrong_type.id not in ids


class TestQueryActiveOnly:
    def test_active_only_excludes_inactive(self, expertise_store: ExpertiseStore) -> None:
        active = _make_record(content="active record")
        inactive = _make_record(content="inactive record")
        expertise_store.insert(active)
        expertise_store.insert(inactive)
        expertise_store.soft_delete(inactive.id)

        results = expertise_store.query(ExpertiseQuery(active_only=True))
        ids = {r.id for r in results}
        assert active.id in ids
        assert inactive.id not in ids

    def test_active_only_false_includes_inactive(self, expertise_store: ExpertiseStore) -> None:
        active = _make_record(content="active record")
        inactive = _make_record(content="inactive record")
        expertise_store.insert(active)
        expertise_store.insert(inactive)
        expertise_store.soft_delete(inactive.id)

        results = expertise_store.query(ExpertiseQuery(active_only=False))
        ids = {r.id for r in results}
        assert active.id in ids
        assert inactive.id in ids


class TestQueryMinConfidence:
    def test_filter_by_min_confidence(self, expertise_store: ExpertiseStore) -> None:
        high_conf = _make_record(content="high confidence", confidence=0.9)
        low_conf = _make_record(content="low confidence", confidence=0.3)
        expertise_store.insert(high_conf)
        expertise_store.insert(low_conf)

        results = expertise_store.query(ExpertiseQuery(min_confidence=0.8))
        ids = {r.id for r in results}
        assert high_conf.id in ids
        assert low_conf.id not in ids


class TestQueryTextSearch:
    def test_text_search_matches_content(self, expertise_store: ExpertiseStore) -> None:
        rec = _make_record(content="always use dependency injection for testability")
        other = _make_record(content="something completely different")
        expertise_store.insert(rec)
        expertise_store.insert(other)

        results = expertise_store.query(ExpertiseQuery(q="dependency injection"))
        ids = {r.id for r in results}
        assert rec.id in ids
        assert other.id not in ids

    def test_text_search_matches_name(self, expertise_store: ExpertiseStore) -> None:
        rec = _make_record(
            content="generic content",
            name="DependencyInjectionPattern",
            type=ExpertiseType.PATTERN,
        )
        expertise_store.insert(rec)

        results = expertise_store.query(ExpertiseQuery(q="DependencyInjection"))
        ids = {r.id for r in results}
        assert rec.id in ids


class TestValidateRecord:
    def test_validate_bumps_count(self, expertise_store: ExpertiseStore) -> None:
        rec = _make_record()
        expertise_store.insert(rec)

        expertise_store.validate_record(rec.id)

        fetched = expertise_store.get(rec.id)
        assert fetched is not None
        assert fetched.validation_count == 2

    def test_validate_updates_timestamp(self, expertise_store: ExpertiseStore) -> None:
        rec = _make_record()
        expertise_store.insert(rec)
        original = expertise_store.get(rec.id)
        assert original is not None
        original_ts = original.last_validated

        time.sleep(0.01)
        expertise_store.validate_record(rec.id)
        updated = expertise_store.get(rec.id)
        assert updated is not None
        assert updated.last_validated >= original_ts

    def test_validate_nonexistent_does_not_raise(self, expertise_store: ExpertiseStore) -> None:
        # DuckDB rowcount is always -1; operation completes without error
        expertise_store.validate_record("exp_doesnotexist")


class TestDomainAutoCreation:
    def test_inserting_creates_domain(self, expertise_store: ExpertiseStore) -> None:
        rec = _make_record(domain="new-domain")
        expertise_store.insert(rec)

        domains = expertise_store.list_domains()
        names = {d["name"] for d in domains}
        assert "new-domain" in names

    def test_domain_record_count_increments(self, expertise_store: ExpertiseStore) -> None:
        for _ in range(3):
            expertise_store.insert(_make_record(domain="counted-domain"))

        domains = {d["name"]: d for d in expertise_store.list_domains()}
        assert domains["counted-domain"]["record_count"] == 3


class TestListDomains:
    def test_list_returns_all_domains(self, expertise_store: ExpertiseStore) -> None:
        for domain in ("alpha", "beta", "gamma"):
            expertise_store.insert(_make_record(domain=domain))

        domains = expertise_store.list_domains()
        names = {d["name"] for d in domains}
        assert {"alpha", "beta", "gamma"}.issubset(names)

    def test_list_returns_required_keys(self, expertise_store: ExpertiseStore) -> None:
        expertise_store.insert(_make_record(domain="check-keys"))
        domains = expertise_store.list_domains()
        entry = next(d for d in domains if d["name"] == "check-keys")
        assert "name" in entry
        assert "description" in entry
        assert "record_count" in entry
        assert "last_updated" in entry


class TestCreateDomain:
    def test_create_domain_explicit(self, expertise_store: ExpertiseStore) -> None:
        expertise_store.create_domain("explicit-domain", description="Created explicitly")
        domains = {d["name"]: d for d in expertise_store.list_domains()}
        assert "explicit-domain" in domains

    def test_create_domain_idempotent(self, expertise_store: ExpertiseStore) -> None:
        expertise_store.create_domain("idempotent-domain")
        expertise_store.create_domain("idempotent-domain")
        domains = expertise_store.list_domains()
        count = sum(1 for d in domains if d["name"] == "idempotent-domain")
        assert count == 1


class TestGetDomainStats:
    def test_stats_correct_aggregations(self, expertise_store: ExpertiseStore) -> None:
        domain = "stats-domain"
        recs = [
            _make_record(domain=domain, type=ExpertiseType.CONVENTION, confidence=1.0),
            _make_record(domain=domain, type=ExpertiseType.PATTERN, confidence=0.8),
            _make_record(domain=domain, type=ExpertiseType.FAILURE, confidence=0.6),
        ]
        for rec in recs:
            expertise_store.insert(rec)
        # soft-delete one
        expertise_store.soft_delete(recs[2].id)

        stats = expertise_store.get_domain_stats(domain)
        assert stats["domain"] == domain
        assert stats["total_records"] == 3
        assert stats["active_records"] == 2
        assert abs(stats["avg_confidence"] - (1.0 + 0.8 + 0.6) / 3) < 1e-6
        assert "by_type" in stats
        by_type = stats["by_type"]
        # only active records in by_type
        assert by_type.get(ExpertiseType.CONVENTION.value, 0) == 1
        assert by_type.get(ExpertiseType.PATTERN.value, 0) == 1
        assert by_type.get(ExpertiseType.FAILURE.value, 0) == 0

    def test_stats_nonexistent_domain(self, expertise_store: ExpertiseStore) -> None:
        stats = expertise_store.get_domain_stats("nonexistent")
        assert stats["domain"] == "nonexistent"
        assert stats["total_records"] == 0
        assert stats["active_records"] == 0


class TestUpdateRecord:
    def test_update_content_field(self, expertise_store: ExpertiseStore) -> None:
        rec = _make_record(content="original content")
        expertise_store.insert(rec)

        expertise_store.update(rec.id, content="updated content")

        fetched = expertise_store.get(rec.id)
        assert fetched is not None
        assert fetched.content == "updated content"

    def test_update_invalid_field_raises(self, expertise_store: ExpertiseStore) -> None:
        rec = _make_record()
        expertise_store.insert(rec)

        with pytest.raises(ValueError):
            expertise_store.update(rec.id, nonexistent_field="value")

    def test_update_no_fields_returns_false(self, expertise_store: ExpertiseStore) -> None:
        rec = _make_record()
        expertise_store.insert(rec)
        result = expertise_store.update(rec.id)
        assert result is False
