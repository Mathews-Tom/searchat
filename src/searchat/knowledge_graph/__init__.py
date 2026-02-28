"""L3 Knowledge Graph — edge store, contradiction detection, resolution, provenance."""
from __future__ import annotations

from searchat.knowledge_graph.detector import ContradictionDetector
from searchat.knowledge_graph.models import (
    ContradictionCandidate,
    EdgeType,
    KnowledgeEdge,
    ResolutionResult,
    ResolutionStrategy,
)
from searchat.knowledge_graph.provenance import ProvenanceTracker
from searchat.knowledge_graph.resolver import ResolutionEngine
from searchat.knowledge_graph.store import KnowledgeGraphStore

__all__ = [
    "EdgeType",
    "KnowledgeEdge",
    "ContradictionCandidate",
    "ResolutionStrategy",
    "ResolutionResult",
    "KnowledgeGraphStore",
    "ContradictionDetector",
    "ResolutionEngine",
    "ProvenanceTracker",
]
