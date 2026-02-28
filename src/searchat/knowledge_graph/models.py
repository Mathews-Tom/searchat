"""Knowledge graph data models for L3 layer."""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum


class EdgeType(str, Enum):
    """Types of directed edges in the knowledge graph."""

    SUPERSEDES = "supersedes"
    CONTRADICTS = "contradicts"
    QUALIFIES = "qualifies"
    DEPENDS_ON = "depends_on"
    DERIVED_FROM = "derived_from"
    RESOLVED = "resolved"


class ResolutionStrategy(str, Enum):
    """Strategies for resolving contradictions."""

    SUPERSEDE = "supersede"
    SCOPE_BOTH = "scope_both"
    MERGE = "merge"
    DISMISS = "dismiss"
    KEEP_BOTH = "keep_both"


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _make_edge_id() -> str:
    return f"edge_{uuid.uuid4().hex[:12]}"


def _make_resolution_id() -> str:
    return f"res_{uuid.uuid4().hex[:12]}"


@dataclass
class KnowledgeEdge:
    """A directed edge between two expertise records."""

    source_id: str
    target_id: str
    edge_type: EdgeType
    id: str = field(default_factory=_make_edge_id)
    metadata: dict | None = None
    created_at: datetime = field(default_factory=_utcnow)
    created_by: str | None = None
    resolution_id: str | None = None


@dataclass
class ContradictionCandidate:
    """A candidate pair flagged as a potential contradiction."""

    record_id_a: str
    record_id_b: str
    similarity_score: float
    contradiction_score: float | None = None
    entailment_score: float | None = None
    neutral_score: float | None = None
    nli_available: bool = True


@dataclass
class ResolutionResult:
    """Result of applying a resolution strategy to a contradiction."""

    strategy: ResolutionStrategy
    resolution_id: str = field(default_factory=_make_resolution_id)
    edge_id: str = ""
    created_edges: list[str] = field(default_factory=list)
    deactivated_records: list[str] = field(default_factory=list)
    new_record_id: str | None = None
    note: str = ""
    resolved_at: datetime = field(default_factory=_utcnow)
