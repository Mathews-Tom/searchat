"""Resolution engine for knowledge graph contradictions."""
from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import TYPE_CHECKING

from searchat.expertise.models import ExpertiseRecord, ExpertiseType
from searchat.knowledge_graph.models import (
    EdgeType,
    KnowledgeEdge,
    ResolutionResult,
    ResolutionStrategy,
)

if TYPE_CHECKING:
    from searchat.expertise.store import ExpertiseStore
    from searchat.knowledge_graph.store import KnowledgeGraphStore

_logger = logging.getLogger(__name__)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _make_record_id() -> str:
    return f"exp_{uuid.uuid4().hex[:12]}"


class ResolutionEngine:
    """Applies resolution strategies to contradiction edges."""

    def __init__(
        self,
        kg_store: KnowledgeGraphStore,
        expertise_store: ExpertiseStore,
        resolved_by: str = "resolution_engine",
    ) -> None:
        self._kg = kg_store
        self._expertise = expertise_store
        self._resolved_by = resolved_by

    # ------------------------------------------------------------------
    # Resolution strategies
    # ------------------------------------------------------------------

    def supersede(self, edge_id: str, winner_id: str) -> ResolutionResult:
        """Deactivate the loser record; create SUPERSEDES edge from winner to loser."""
        edge = self._kg.get_edge(edge_id)
        if edge is None:
            raise ValueError(f"Edge not found: {edge_id}")

        loser_id = edge.target_id if edge.source_id == winner_id else edge.source_id
        result = ResolutionResult(strategy=ResolutionStrategy.SUPERSEDE, edge_id=edge_id)

        # Mark CONTRADICTS edge as resolved
        self._kg.update_edge(edge_id, resolution_id=result.resolution_id)

        # Create SUPERSEDES edge: winner → loser
        supersedes_edge = KnowledgeEdge(
            source_id=winner_id,
            target_id=loser_id,
            edge_type=EdgeType.SUPERSEDES,
            created_by=self._resolved_by,
            resolution_id=result.resolution_id,
            metadata={"resolution_strategy": ResolutionStrategy.SUPERSEDE.value},
        )
        self._kg.create_edge(supersedes_edge)
        result.created_edges.append(supersedes_edge.id)

        # Soft-delete the losing record
        self._expertise.soft_delete(loser_id)
        result.deactivated_records.append(loser_id)
        result.note = f"Record {winner_id} supersedes {loser_id}"

        _logger.info("supersede: %s wins over %s (edge=%s)", winner_id, loser_id, edge_id)
        return result

    def scope_both(
        self,
        edge_id: str,
        scope_a: str,
        scope_b: str,
    ) -> ResolutionResult:
        """Qualify each record's content with its applicable scope."""
        edge = self._kg.get_edge(edge_id)
        if edge is None:
            raise ValueError(f"Edge not found: {edge_id}")

        result = ResolutionResult(strategy=ResolutionStrategy.SCOPE_BOTH, edge_id=edge_id)

        # Mark CONTRADICTS edge as resolved
        self._kg.update_edge(edge_id, resolution_id=result.resolution_id)

        # Append scope qualifiers to both records' content
        record_a = self._expertise.get(edge.source_id)
        record_b = self._expertise.get(edge.target_id)

        if record_a is not None:
            new_content_a = f"{record_a.content} [Scope: {scope_a}]"
            self._expertise.update(edge.source_id, content=new_content_a)

        if record_b is not None:
            new_content_b = f"{record_b.content} [Scope: {scope_b}]"
            self._expertise.update(edge.target_id, content=new_content_b)

        # Create QUALIFIES edges to encode the scoping relationship
        qual_a = KnowledgeEdge(
            source_id=edge.source_id,
            target_id=edge.target_id,
            edge_type=EdgeType.QUALIFIES,
            created_by=self._resolved_by,
            resolution_id=result.resolution_id,
            metadata={
                "resolution_strategy": ResolutionStrategy.SCOPE_BOTH.value,
                "scope_a": scope_a,
                "scope_b": scope_b,
            },
        )
        self._kg.create_edge(qual_a)
        result.created_edges.append(qual_a.id)
        result.note = f"Both records scoped: '{scope_a}' vs '{scope_b}'"

        _logger.info("scope_both: edge=%s scoped as '%s' / '%s'", edge_id, scope_a, scope_b)
        return result

    def merge(self, edge_id: str, merged_content: str) -> ResolutionResult:
        """Create a merged record, deactivate both originals."""
        edge = self._kg.get_edge(edge_id)
        if edge is None:
            raise ValueError(f"Edge not found: {edge_id}")

        result = ResolutionResult(strategy=ResolutionStrategy.MERGE, edge_id=edge_id)

        # Mark CONTRADICTS edge as resolved
        self._kg.update_edge(edge_id, resolution_id=result.resolution_id)

        record_a = self._expertise.get(edge.source_id)
        record_b = self._expertise.get(edge.target_id)

        # Derive metadata from record_a as the base
        base = record_a or record_b
        if base is None:
            raise ValueError(
                f"Neither record found: {edge.source_id}, {edge.target_id}"
            )

        merged_record = ExpertiseRecord(
            id=_make_record_id(),
            type=base.type,
            domain=base.domain,
            project=base.project,
            content=merged_content,
            source_agent=self._resolved_by,
            tags=list({*base.tags, *(record_b.tags if record_b else [])}),
            confidence=min(
                base.confidence,
                record_b.confidence if record_b else base.confidence,
            ),
        )
        self._expertise.insert(merged_record)
        result.new_record_id = merged_record.id

        # Soft-delete both originals
        for rec_id in (edge.source_id, edge.target_id):
            self._expertise.soft_delete(rec_id)
            result.deactivated_records.append(rec_id)

        # SUPERSEDES edges: merged → originals
        for original_id in (edge.source_id, edge.target_id):
            sup_edge = KnowledgeEdge(
                source_id=merged_record.id,
                target_id=original_id,
                edge_type=EdgeType.SUPERSEDES,
                created_by=self._resolved_by,
                resolution_id=result.resolution_id,
                metadata={"resolution_strategy": ResolutionStrategy.MERGE.value},
            )
            self._kg.create_edge(sup_edge)
            result.created_edges.append(sup_edge.id)

        result.note = f"Merged into {merged_record.id}"
        _logger.info("merge: created %s from %s + %s", merged_record.id, edge.source_id, edge.target_id)
        return result

    def dismiss(self, edge_id: str, reason: str) -> ResolutionResult:
        """Mark the CONTRADICTS edge as RESOLVED (false positive)."""
        edge = self._kg.get_edge(edge_id)
        if edge is None:
            raise ValueError(f"Edge not found: {edge_id}")

        result = ResolutionResult(strategy=ResolutionStrategy.DISMISS, edge_id=edge_id)

        # Create audit RESOLVED edge
        resolved_edge = KnowledgeEdge(
            source_id=edge.source_id,
            target_id=edge.target_id,
            edge_type=EdgeType.RESOLVED,
            created_by=self._resolved_by,
            resolution_id=result.resolution_id,
            metadata={
                "resolution_strategy": ResolutionStrategy.DISMISS.value,
                "reason": reason,
                "original_edge_id": edge_id,
            },
        )
        self._kg.create_edge(resolved_edge)
        result.created_edges.append(resolved_edge.id)

        self._kg.update_edge(edge_id, resolution_id=result.resolution_id)
        result.note = f"Dismissed as false positive: {reason}"

        _logger.info("dismiss: edge=%s dismissed (%s)", edge_id, reason)
        return result

    def keep_both(self, edge_id: str, reason: str) -> ResolutionResult:
        """Acknowledge the contradiction; keep both records active."""
        edge = self._kg.get_edge(edge_id)
        if edge is None:
            raise ValueError(f"Edge not found: {edge_id}")

        result = ResolutionResult(strategy=ResolutionStrategy.KEEP_BOTH, edge_id=edge_id)

        resolved_edge = KnowledgeEdge(
            source_id=edge.source_id,
            target_id=edge.target_id,
            edge_type=EdgeType.RESOLVED,
            created_by=self._resolved_by,
            resolution_id=result.resolution_id,
            metadata={
                "resolution_strategy": ResolutionStrategy.KEEP_BOTH.value,
                "reason": reason,
                "original_edge_id": edge_id,
            },
        )
        self._kg.create_edge(resolved_edge)
        result.created_edges.append(resolved_edge.id)

        self._kg.update_edge(edge_id, resolution_id=result.resolution_id)
        result.note = f"Both records kept, contradiction acknowledged: {reason}"

        _logger.info("keep_both: edge=%s acknowledged (%s)", edge_id, reason)
        return result
