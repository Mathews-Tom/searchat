"""Expertise data models for the L2 knowledge layer."""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum


class ExpertiseType(str, Enum):
    """Types of expertise records."""

    CONVENTION = "convention"
    PATTERN = "pattern"
    FAILURE = "failure"
    DECISION = "decision"
    BOUNDARY = "boundary"
    INSIGHT = "insight"


class ExpertiseSeverity(str, Enum):
    """Severity levels for failures and boundaries."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class RecordAction(str, Enum):
    """Outcome of a record operation."""

    CREATED = "created"
    REINFORCED = "reinforced"
    DUPLICATE_FLAGGED = "duplicate_flagged"


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _make_id() -> str:
    return f"exp_{uuid.uuid4().hex[:12]}"


@dataclass
class ExpertiseRecord:
    """A single expertise record in the knowledge store."""

    type: ExpertiseType
    domain: str
    content: str
    project: str | None = None
    id: str = field(default_factory=_make_id)
    confidence: float = 1.0
    source_conversation_id: str | None = None
    source_agent: str | None = None
    tags: list[str] = field(default_factory=list)
    severity: ExpertiseSeverity | None = None
    created_at: datetime = field(default_factory=_utcnow)
    last_validated: datetime = field(default_factory=_utcnow)
    validation_count: int = 1
    is_active: bool = True
    # Pattern-specific
    name: str | None = None
    example: str | None = None
    # Decision-specific
    rationale: str | None = None
    alternatives_considered: list[str] | None = None
    # Failure-specific
    resolution: str | None = None


@dataclass
class ExpertiseQuery:
    """Filter parameters for querying expertise records."""

    domain: str | None = None
    type: ExpertiseType | None = None
    project: str | None = None
    tags: list[str] | None = None
    severity: ExpertiseSeverity | None = None
    min_confidence: float | None = None
    active_only: bool = True
    after: datetime | None = None
    agent: str | None = None
    q: str | None = None
    limit: int = 50
    offset: int = 0


@dataclass
class PrimeResult:
    """Result of priority-ranked token-budgeted priming."""

    expertise: list[ExpertiseRecord]
    token_count: int
    domains_covered: list[str]
    records_total: int
    records_included: int
    records_filtered_inactive: int


@dataclass
class RecordResult:
    """Outcome of recording new expertise."""

    record: ExpertiseRecord
    action: RecordAction
    existing_id: str | None = None
