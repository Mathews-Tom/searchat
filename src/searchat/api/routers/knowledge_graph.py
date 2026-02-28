"""REST API router for the L3 Knowledge Graph."""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from searchat.api.dependencies import get_knowledge_graph_store, get_expertise_store, get_config
from searchat.knowledge_graph.models import EdgeType, KnowledgeEdge, ResolutionStrategy

router = APIRouter(prefix="/api/knowledge-graph", tags=["knowledge_graph"])


# ---------------------------------------------------------------------------
# Pydantic request/response models
# ---------------------------------------------------------------------------


class EdgeResponse(BaseModel):
    id: str
    source_id: str
    target_id: str
    edge_type: str
    metadata: dict[str, Any] | None
    created_at: str
    created_by: str | None
    resolution_id: str | None


class ContradictionResponse(BaseModel):
    edge_id: str
    record_id_a: str
    record_id_b: str
    created_at: str
    metadata: dict[str, Any] | None
    resolution_id: str | None


class ContradictionListResponse(BaseModel):
    results: list[ContradictionResponse]
    total: int
    unresolved_only: bool


class ResolutionRequest(BaseModel):
    edge_id: str = Field(..., min_length=1)
    strategy: str = Field(
        ...,
        description="Resolution strategy: supersede|scope_both|merge|dismiss|keep_both",
    )
    params: dict[str, Any] = Field(default_factory=dict)


class ResolutionResponse(BaseModel):
    strategy: str
    resolution_id: str
    edge_id: str
    created_edges: list[str]
    deactivated_records: list[str]
    new_record_id: str | None
    note: str
    resolved_at: str


class LineageResponse(BaseModel):
    record_id: str
    conversations: list[str]
    derived_records: list[str]


class RelatedRecordsResponse(BaseModel):
    record_id: str
    edges: list[EdgeResponse]
    total: int


class GraphStatsResponse(BaseModel):
    node_count: int
    edge_count: int
    contradiction_count: int
    unresolved_contradiction_count: int
    contradiction_rate: float
    health_score: float
    edge_type_counts: dict[str, int]


class EdgeCreateRequest(BaseModel):
    source_id: str = Field(..., min_length=1)
    target_id: str = Field(..., min_length=1)
    edge_type: str = Field(
        ...,
        description="Edge type: supersedes|contradicts|qualifies|depends_on|derived_from|resolved",
    )
    metadata: dict[str, Any] | None = None
    created_by: str | None = None


class DomainMapEntry(BaseModel):
    source_domain: str
    target_domain: str
    edge_type: str
    edge_count: int


class DomainMapResponse(BaseModel):
    entries: list[DomainMapEntry]
    domains: list[str]
    total_cross_domain_edges: int


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _edge_to_response(edge: KnowledgeEdge) -> EdgeResponse:
    return EdgeResponse(
        id=edge.id,
        source_id=edge.source_id,
        target_id=edge.target_id,
        edge_type=edge.edge_type.value,
        metadata=edge.metadata,
        created_at=edge.created_at.isoformat(),
        created_by=edge.created_by,
        resolution_id=edge.resolution_id,
    )


def _parse_edge_type(value: str) -> EdgeType:
    try:
        return EdgeType(value)
    except ValueError:
        valid = ", ".join(t.value for t in EdgeType)
        raise HTTPException(422, f"Invalid edge_type '{value}'. Must be one of: {valid}")


def _parse_resolution_strategy(value: str) -> ResolutionStrategy:
    try:
        return ResolutionStrategy(value)
    except ValueError:
        valid = ", ".join(s.value for s in ResolutionStrategy)
        raise HTTPException(422, f"Invalid strategy '{value}'. Must be one of: {valid}")


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.get("/contradictions", response_model=ContradictionListResponse)
def list_contradictions(
    domain: str | None = Query(None),
    project: str | None = Query(None),
    unresolved_only: bool = Query(True),
) -> ContradictionListResponse:
    """List contradiction edges, optionally filtered by domain or project."""
    kg_store = get_knowledge_graph_store()
    contradiction_edges = kg_store.get_contradictions(unresolved_only=unresolved_only)

    # Filter by domain/project via expertise store if filters requested
    if domain is not None or project is not None:
        expertise_store = get_expertise_store()
        filtered: list[KnowledgeEdge] = []
        for edge in contradiction_edges:
            rec_a = expertise_store.get(edge.source_id)
            rec_b = expertise_store.get(edge.target_id)
            if domain is not None:
                if (rec_a is None or rec_a.domain != domain) and (
                    rec_b is None or rec_b.domain != domain
                ):
                    continue
            if project is not None:
                if (rec_a is None or rec_a.project != project) and (
                    rec_b is None or rec_b.project != project
                ):
                    continue
            filtered.append(edge)
        contradiction_edges = filtered

    results = [
        ContradictionResponse(
            edge_id=e.id,
            record_id_a=e.source_id,
            record_id_b=e.target_id,
            created_at=e.created_at.isoformat(),
            metadata=e.metadata,
            resolution_id=e.resolution_id,
        )
        for e in contradiction_edges
    ]
    return ContradictionListResponse(
        results=results,
        total=len(results),
        unresolved_only=unresolved_only,
    )


@router.post("/resolve", response_model=ResolutionResponse)
def resolve_contradiction(body: ResolutionRequest) -> ResolutionResponse:
    """Apply a resolution strategy to a contradiction edge."""
    kg_store = get_knowledge_graph_store()
    expertise_store = get_expertise_store()

    edge = kg_store.get_edge(body.edge_id)
    if edge is None:
        raise HTTPException(404, f"Edge not found: {body.edge_id}")
    if edge.edge_type != EdgeType.CONTRADICTS:
        raise HTTPException(
            422, f"Edge {body.edge_id} is not a CONTRADICTS edge (type={edge.edge_type.value})"
        )

    strategy = _parse_resolution_strategy(body.strategy)

    from searchat.knowledge_graph.resolver import ResolutionEngine

    engine = ResolutionEngine(kg_store=kg_store, expertise_store=expertise_store)

    params = body.params
    if strategy == ResolutionStrategy.SUPERSEDE:
        winner_id = params.get("winner_id")
        if not winner_id:
            raise HTTPException(422, "params.winner_id required for supersede strategy")
        result = engine.supersede(body.edge_id, winner_id)
    elif strategy == ResolutionStrategy.SCOPE_BOTH:
        scope_a = params.get("scope_a", "")
        scope_b = params.get("scope_b", "")
        if not scope_a or not scope_b:
            raise HTTPException(422, "params.scope_a and params.scope_b required for scope_both strategy")
        result = engine.scope_both(body.edge_id, scope_a, scope_b)
    elif strategy == ResolutionStrategy.MERGE:
        merged_content = params.get("merged_content", "")
        if not merged_content:
            raise HTTPException(422, "params.merged_content required for merge strategy")
        result = engine.merge(body.edge_id, merged_content)
    elif strategy == ResolutionStrategy.DISMISS:
        reason = params.get("reason", "")
        if not reason:
            raise HTTPException(422, "params.reason required for dismiss strategy")
        result = engine.dismiss(body.edge_id, reason)
    elif strategy == ResolutionStrategy.KEEP_BOTH:
        reason = params.get("reason", "")
        if not reason:
            raise HTTPException(422, "params.reason required for keep_both strategy")
        result = engine.keep_both(body.edge_id, reason)
    else:
        raise HTTPException(422, f"Unsupported strategy: {strategy}")

    return ResolutionResponse(
        strategy=result.strategy.value,
        resolution_id=result.resolution_id,
        edge_id=result.edge_id,
        created_edges=result.created_edges,
        deactivated_records=result.deactivated_records,
        new_record_id=result.new_record_id,
        note=result.note,
        resolved_at=result.resolved_at.isoformat(),
    )


@router.get("/lineage/{record_id}", response_model=LineageResponse)
def get_lineage(record_id: str) -> LineageResponse:
    """Trace a record's provenance back to source conversations."""
    kg_store = get_knowledge_graph_store()
    expertise_store = get_expertise_store()

    record = expertise_store.get(record_id)
    if record is None:
        raise HTTPException(404, f"Record not found: {record_id}")

    from searchat.knowledge_graph.provenance import ProvenanceTracker

    tracker = ProvenanceTracker(kg_store=kg_store)
    lineage = tracker.get_full_lineage(record_id)

    return LineageResponse(
        record_id=record_id,
        conversations=lineage.get("conversations", []),
        derived_records=lineage.get("derived_records", []),
    )


@router.get("/related/{record_id}", response_model=RelatedRecordsResponse)
def get_related(
    record_id: str,
    edge_types: str | None = Query(None, description="Comma-separated edge type list"),
    limit: int = Query(20, ge=1, le=200),
) -> RelatedRecordsResponse:
    """Return all records connected to a given record (1-hop)."""
    kg_store = get_knowledge_graph_store()
    expertise_store = get_expertise_store()

    record = expertise_store.get(record_id)
    if record is None:
        raise HTTPException(404, f"Record not found: {record_id}")

    parsed_types: list[EdgeType] | None = None
    if edge_types:
        parsed_types = [_parse_edge_type(t.strip()) for t in edge_types.split(",") if t.strip()]

    edges = kg_store.get_related(record_id, edge_types=parsed_types, limit=limit)
    return RelatedRecordsResponse(
        record_id=record_id,
        edges=[_edge_to_response(e) for e in edges],
        total=len(edges),
    )


@router.get("/stats", response_model=GraphStatsResponse)
def graph_stats() -> GraphStatsResponse:
    """Return node/edge counts, contradiction rate, and health score."""
    kg_store = get_knowledge_graph_store()
    expertise_store = get_expertise_store()

    from searchat.expertise.models import ExpertiseQuery

    all_records = expertise_store.query(ExpertiseQuery(active_only=False, limit=100000))
    node_count = len(all_records)

    all_contradictions = kg_store.get_contradictions(unresolved_only=False)
    unresolved = kg_store.get_contradictions(unresolved_only=True)
    contradiction_count = len(all_contradictions)
    unresolved_contradiction_count = len(unresolved)

    # Tally edges by type
    edge_type_counts: dict[str, int] = {t.value: 0 for t in EdgeType}
    total_edges = 0
    for record in all_records:
        edges = kg_store.get_edges_for_record(record.id)
        for edge in edges:
            # Count each edge once (source side only)
            if edge.source_id == record.id:
                edge_type_counts[edge.edge_type.value] += 1
                total_edges += 1

    contradiction_rate = (
        contradiction_count / node_count if node_count > 0 else 0.0
    )
    # Health: 1.0 = no unresolved contradictions, degrades proportionally
    health_score = max(
        0.0,
        1.0 - (unresolved_contradiction_count / node_count if node_count > 0 else 0.0),
    )

    return GraphStatsResponse(
        node_count=node_count,
        edge_count=total_edges,
        contradiction_count=contradiction_count,
        unresolved_contradiction_count=unresolved_contradiction_count,
        contradiction_rate=round(contradiction_rate, 4),
        health_score=round(health_score, 4),
        edge_type_counts=edge_type_counts,
    )


@router.get("/domain-map", response_model=DomainMapResponse)
def domain_map() -> DomainMapResponse:
    """Return cross-domain relationship data."""
    kg_store = get_knowledge_graph_store()
    expertise_store = get_expertise_store()

    from searchat.expertise.models import ExpertiseQuery

    all_records = expertise_store.query(ExpertiseQuery(active_only=False, limit=100000))
    record_domain: dict[str, str] = {r.id: r.domain for r in all_records}
    domains: set[str] = {r.domain for r in all_records}

    counts: dict[tuple[str, str, str], int] = {}
    for record in all_records:
        edges = kg_store.get_edges_for_record(record.id, as_source=True, as_target=False)
        for edge in edges:
            src_domain = record_domain.get(edge.source_id)
            tgt_domain = record_domain.get(edge.target_id)
            if src_domain is None or tgt_domain is None:
                continue
            key = (src_domain, tgt_domain, edge.edge_type.value)
            counts[key] = counts.get(key, 0) + 1

    entries = [
        DomainMapEntry(
            source_domain=src,
            target_domain=tgt,
            edge_type=etype,
            edge_count=cnt,
        )
        for (src, tgt, etype), cnt in sorted(counts.items())
    ]
    cross_domain_total = sum(
        cnt for (src, tgt, _), cnt in counts.items() if src != tgt
    )

    return DomainMapResponse(
        entries=entries,
        domains=sorted(domains),
        total_cross_domain_edges=cross_domain_total,
    )


@router.post("/edges", response_model=EdgeResponse, status_code=201)
def create_edge(body: EdgeCreateRequest) -> EdgeResponse:
    """Create a manual edge between two expertise records."""
    kg_store = get_knowledge_graph_store()
    expertise_store = get_expertise_store()

    if expertise_store.get(body.source_id) is None:
        raise HTTPException(404, f"Source record not found: {body.source_id}")
    if expertise_store.get(body.target_id) is None:
        raise HTTPException(404, f"Target record not found: {body.target_id}")

    edge_type = _parse_edge_type(body.edge_type)
    edge = KnowledgeEdge(
        source_id=body.source_id,
        target_id=body.target_id,
        edge_type=edge_type,
        metadata=body.metadata,
        created_by=body.created_by,
    )
    kg_store.create_edge(edge)
    return _edge_to_response(edge)


@router.delete("/edges/{edge_id}", status_code=200)
def delete_edge(edge_id: str) -> dict[str, str]:
    """Remove an edge from the knowledge graph."""
    kg_store = get_knowledge_graph_store()
    edge = kg_store.get_edge(edge_id)
    if edge is None:
        raise HTTPException(404, f"Edge not found: {edge_id}")
    kg_store.delete_edge(edge_id)
    return {"status": "deleted", "id": edge_id}
