"""Tests for expertise data models."""
from __future__ import annotations

import pytest

from searchat.expertise.models import (
    ExpertiseQuery,
    ExpertiseRecord,
    ExpertiseSeverity,
    ExpertiseType,
    PrimeResult,
    RecordAction,
    RecordResult,
)


class TestExpertiseType:
    def test_has_six_values(self) -> None:
        assert len(ExpertiseType) == 6

    def test_all_values(self) -> None:
        expected = {"convention", "pattern", "failure", "decision", "boundary", "insight"}
        assert {e.value for e in ExpertiseType} == expected

    def test_is_string_enum(self) -> None:
        assert ExpertiseType.CONVENTION == "convention"


class TestExpertiseSeverity:
    def test_has_four_values(self) -> None:
        assert len(ExpertiseSeverity) == 4

    def test_all_values(self) -> None:
        expected = {"low", "medium", "high", "critical"}
        assert {e.value for e in ExpertiseSeverity} == expected


class TestRecordAction:
    def test_has_three_values(self) -> None:
        assert len(RecordAction) == 3

    def test_all_values(self) -> None:
        expected = {"created", "reinforced", "duplicate_flagged"}
        assert {e.value for e in RecordAction} == expected


class TestExpertiseRecord:
    def test_minimal_creation(self) -> None:
        rec = ExpertiseRecord(
            type=ExpertiseType.CONVENTION,
            domain="python",
            content="Use type hints everywhere",
        )
        assert rec.type == ExpertiseType.CONVENTION
        assert rec.domain == "python"
        assert rec.content == "Use type hints everywhere"

    def test_defaults(self) -> None:
        rec = ExpertiseRecord(
            type=ExpertiseType.PATTERN,
            domain="api",
            content="Always validate input at boundaries",
        )
        assert rec.confidence == 1.0
        assert rec.validation_count == 1
        assert rec.is_active is True
        assert rec.project is None
        assert rec.severity is None
        assert rec.tags == []
        assert rec.source_conversation_id is None
        assert rec.source_agent is None

    def test_auto_generated_id(self) -> None:
        rec = ExpertiseRecord(
            type=ExpertiseType.INSIGHT,
            domain="design",
            content="Prefer composition over inheritance",
        )
        assert rec.id.startswith("exp_")
        assert len(rec.id) == 16  # "exp_" + 12 hex chars

    def test_two_records_have_different_ids(self) -> None:
        r1 = ExpertiseRecord(type=ExpertiseType.FAILURE, domain="d", content="c")
        r2 = ExpertiseRecord(type=ExpertiseType.FAILURE, domain="d", content="c")
        assert r1.id != r2.id

    def test_all_fields(self) -> None:
        rec = ExpertiseRecord(
            type=ExpertiseType.DECISION,
            domain="architecture",
            content="Use event sourcing for audit trail",
            project="my-project",
            id="exp_custom000001",
            confidence=0.85,
            source_conversation_id="conv-abc",
            source_agent="claude-opus-4-6",
            tags=["architecture", "events"],
            severity=ExpertiseSeverity.HIGH,
            name="EventSourcingDecision",
            example="See OrderService for reference",
            rationale="Needed for regulatory compliance",
            alternatives_considered=["CQRS only", "traditional CRUD"],
            resolution=None,
            validation_count=3,
            is_active=True,
        )
        assert rec.project == "my-project"
        assert rec.confidence == 0.85
        assert rec.source_conversation_id == "conv-abc"
        assert rec.source_agent == "claude-opus-4-6"
        assert rec.tags == ["architecture", "events"]
        assert rec.severity == ExpertiseSeverity.HIGH
        assert rec.name == "EventSourcingDecision"
        assert rec.rationale == "Needed for regulatory compliance"
        assert rec.alternatives_considered == ["CQRS only", "traditional CRUD"]
        assert rec.validation_count == 3

    def test_created_at_and_last_validated_set(self) -> None:
        from datetime import datetime, timezone

        rec = ExpertiseRecord(type=ExpertiseType.BOUNDARY, domain="d", content="c")
        assert isinstance(rec.created_at, datetime)
        assert rec.created_at.tzinfo == timezone.utc
        assert isinstance(rec.last_validated, datetime)


class TestExpertiseQuery:
    def test_defaults(self) -> None:
        q = ExpertiseQuery()
        assert q.active_only is True
        assert q.limit == 50
        assert q.offset == 0
        assert q.domain is None
        assert q.type is None
        assert q.project is None
        assert q.tags is None
        assert q.severity is None
        assert q.min_confidence is None
        assert q.after is None
        assert q.agent is None
        assert q.q is None

    def test_custom_values(self) -> None:
        q = ExpertiseQuery(
            domain="python",
            type=ExpertiseType.PATTERN,
            active_only=False,
            limit=10,
            offset=5,
        )
        assert q.domain == "python"
        assert q.type == ExpertiseType.PATTERN
        assert q.active_only is False
        assert q.limit == 10
        assert q.offset == 5


class TestPrimeResult:
    def test_creation(self) -> None:
        records = [
            ExpertiseRecord(type=ExpertiseType.INSIGHT, domain="d", content="c")
        ]
        result = PrimeResult(
            expertise=records,
            token_count=200,
            domains_covered=["python", "api"],
            records_total=10,
            records_included=1,
            records_filtered_inactive=2,
        )
        assert result.expertise == records
        assert result.token_count == 200
        assert result.domains_covered == ["python", "api"]
        assert result.records_total == 10
        assert result.records_included == 1
        assert result.records_filtered_inactive == 2


class TestRecordResult:
    def test_creation_created(self) -> None:
        rec = ExpertiseRecord(type=ExpertiseType.CONVENTION, domain="d", content="c")
        result = RecordResult(record=rec, action=RecordAction.CREATED)
        assert result.record is rec
        assert result.action == RecordAction.CREATED
        assert result.existing_id is None

    def test_creation_reinforced(self) -> None:
        rec = ExpertiseRecord(type=ExpertiseType.PATTERN, domain="d", content="c")
        result = RecordResult(
            record=rec, action=RecordAction.REINFORCED, existing_id="exp_abc123456789"
        )
        assert result.action == RecordAction.REINFORCED
        assert result.existing_id == "exp_abc123456789"

    def test_creation_duplicate_flagged(self) -> None:
        rec = ExpertiseRecord(type=ExpertiseType.FAILURE, domain="d", content="c")
        result = RecordResult(
            record=rec,
            action=RecordAction.DUPLICATE_FLAGGED,
            existing_id="exp_dup000000001",
        )
        assert result.action == RecordAction.DUPLICATE_FLAGGED
