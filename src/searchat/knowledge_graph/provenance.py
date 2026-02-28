"""Provenance tracking: DERIVED_FROM edges for expertise lineage."""
from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from searchat.expertise.models import ExpertiseRecord
from searchat.knowledge_graph.models import EdgeType, KnowledgeEdge

if TYPE_CHECKING:
    from searchat.knowledge_graph.store import KnowledgeGraphStore

_logger = logging.getLogger(__name__)


class ProvenanceTracker:
    """Auto-creates and queries DERIVED_FROM edges for expertise provenance."""

    def __init__(self, kg_store: KnowledgeGraphStore, created_by: str = "provenance_tracker") -> None:
        self._kg = kg_store
        self._created_by = created_by

    def record_extraction(
        self,
        record: ExpertiseRecord,
        conversation_id: str,
        agent: str | None = None,
    ) -> str:
        """Create a DERIVED_FROM edge: expertise_record → conversation.

        Returns the edge ID.
        """
        edge = KnowledgeEdge(
            source_id=record.id,
            target_id=conversation_id,
            edge_type=EdgeType.DERIVED_FROM,
            created_by=agent or self._created_by,
            metadata={
                "conversation_id": conversation_id,
                "record_domain": record.domain,
                "record_type": record.type.value,
                "source_agent": record.source_agent,
            },
        )
        self._kg.create_edge(edge)
        _logger.debug(
            "provenance: %s derived from conversation %s", record.id, conversation_id
        )
        return edge.id

    def get_conversations_for_record(self, record_id: str) -> list[str]:
        """Return all conversation IDs that the given expertise record was derived from."""
        edges = self._kg.get_edges_for_record(
            record_id,
            edge_type=EdgeType.DERIVED_FROM,
            as_source=True,
            as_target=False,
        )
        return [e.target_id for e in edges]

    def get_records_from_conversation(self, conversation_id: str) -> list[str]:
        """Return all expertise record IDs derived from the given conversation."""
        edges = self._kg.get_edges_for_record(
            conversation_id,
            edge_type=EdgeType.DERIVED_FROM,
            as_source=False,
            as_target=True,
        )
        return [e.source_id for e in edges]

    def get_full_lineage(self, record_id: str) -> dict[str, list[str]]:
        """Return forward and reverse lineage for a record.

        Returns:
            {
                "conversations": [...],   # conversations this record came from
                "derived_records": [...], # records that were derived from this record's sources
            }
        """
        conversations = self.get_conversations_for_record(record_id)

        # For each source conversation, find sibling records (forward lineage)
        sibling_record_ids: list[str] = []
        for conv_id in conversations:
            siblings = self.get_records_from_conversation(conv_id)
            for sid in siblings:
                if sid != record_id and sid not in sibling_record_ids:
                    sibling_record_ids.append(sid)

        return {
            "conversations": conversations,
            "derived_records": sibling_record_ids,
        }
