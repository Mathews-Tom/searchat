"""REST API router for the L2 Expertise Store."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from searchat.api.dependencies import get_expertise_store, get_config
from searchat.expertise.models import (
    ExpertiseQuery,
    ExpertiseRecord,
    ExpertiseSeverity,
    ExpertiseType,
    RecordAction,
    RecordResult,
)
from searchat.expertise.primer import ExpertisePrioritizer, PrimeFormatter
from searchat.expertise.staleness import StalenessManager, compute_staleness

router = APIRouter(prefix="/api/expertise", tags=["expertise"])


# ---------------------------------------------------------------------------
# Pydantic request/response models
# ---------------------------------------------------------------------------


class ExpertiseCreateRequest(BaseModel):
    type: str = Field(..., description="Record type: convention|pattern|failure|decision|boundary|insight")
    domain: str = Field(..., min_length=1)
    content: str = Field(..., min_length=1)
    project: str | None = None
    severity: str | None = None
    tags: list[str] = Field(default_factory=list)
    name: str | None = None
    example: str | None = None
    rationale: str | None = None
    alternatives_considered: list[str] | None = None
    resolution: str | None = None
    source_conversation_id: str | None = None
    source_agent: str | None = None
    confidence: float = 1.0


class ExpertiseUpdateRequest(BaseModel):
    content: str | None = None
    domain: str | None = None
    project: str | None = None
    severity: str | None = None
    tags: list[str] | None = None
    name: str | None = None
    example: str | None = None
    rationale: str | None = None
    resolution: str | None = None
    confidence: float | None = None
    is_active: bool | None = None


class ExpertiseResponse(BaseModel):
    id: str
    type: str
    domain: str
    content: str
    project: str | None
    confidence: float
    source_conversation_id: str | None
    source_agent: str | None
    tags: list[str]
    severity: str | None
    created_at: str
    last_validated: str
    validation_count: int
    is_active: bool
    name: str | None
    example: str | None
    rationale: str | None
    alternatives_considered: list[str] | None
    resolution: str | None


class ExpertiseListResponse(BaseModel):
    results: list[ExpertiseResponse]
    total: int
    filters: dict[str, Any]


class DomainCreateRequest(BaseModel):
    name: str = Field(..., min_length=1)
    description: str = ""


class DomainResponse(BaseModel):
    name: str
    description: str | None
    record_count: int
    last_updated: str | None


class RecordResultResponse(BaseModel):
    record: ExpertiseResponse
    action: str
    existing_id: str | None


class ExtractionRequest(BaseModel):
    text: str = Field(..., min_length=1)
    domain: str = "general"
    project: str | None = None
    conversation_id: str | None = None
    mode: str = Field("heuristic_only", description="heuristic_only|full|llm_only")


class ExtractionResponse(BaseModel):
    conversations_processed: int
    records_created: int
    records_reinforced: int
    records_flagged: int
    heuristic_extracted: int
    llm_extracted: int
    errors: list[str]


class StatusResponse(BaseModel):
    total_records: int
    active_records: int
    domains: list[dict[str, Any]]


class StaleRecordResponse(BaseModel):
    record: ExpertiseResponse
    staleness_score: float


class StaleListResponse(BaseModel):
    results: list[StaleRecordResponse]
    total: int
    threshold: float


class PruneRequest(BaseModel):
    threshold: float | None = None
    dry_run: bool = True


class PruneResultResponse(BaseModel):
    pruned_count: int
    skipped_count: int
    total_evaluated: int
    dry_run: bool
    pruned_ids: list[str]
    skipped_ids: list[str]


class DomainPatchRequest(BaseModel):
    new_name: str | None = None
    description: str | None = None
    merge_into: str | None = None


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _record_to_response(r: ExpertiseRecord) -> ExpertiseResponse:
    return ExpertiseResponse(
        id=r.id,
        type=r.type.value,
        domain=r.domain,
        content=r.content,
        project=r.project,
        confidence=r.confidence,
        source_conversation_id=r.source_conversation_id,
        source_agent=r.source_agent,
        tags=r.tags,
        severity=r.severity.value if r.severity else None,
        created_at=r.created_at.isoformat(),
        last_validated=r.last_validated.isoformat(),
        validation_count=r.validation_count,
        is_active=r.is_active,
        name=r.name,
        example=r.example,
        rationale=r.rationale,
        alternatives_considered=r.alternatives_considered,
        resolution=r.resolution,
    )


def _parse_type(value: str) -> ExpertiseType:
    try:
        return ExpertiseType(value)
    except ValueError:
        valid = ", ".join(t.value for t in ExpertiseType)
        raise HTTPException(422, f"Invalid type '{value}'. Must be one of: {valid}")


def _parse_severity(value: str | None) -> ExpertiseSeverity | None:
    if value is None:
        return None
    try:
        return ExpertiseSeverity(value)
    except ValueError:
        valid = ", ".join(s.value for s in ExpertiseSeverity)
        raise HTTPException(422, f"Invalid severity '{value}'. Must be one of: {valid}")


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.post("", response_model=RecordResultResponse, status_code=201)
def create_expertise(body: ExpertiseCreateRequest) -> RecordResultResponse:
    """Record new expertise with deduplication."""
    store = get_expertise_store()
    record = ExpertiseRecord(
        type=_parse_type(body.type),
        domain=body.domain,
        content=body.content,
        project=body.project,
        severity=_parse_severity(body.severity),
        tags=body.tags,
        name=body.name,
        example=body.example,
        rationale=body.rationale,
        alternatives_considered=body.alternatives_considered,
        resolution=body.resolution,
        source_conversation_id=body.source_conversation_id,
        source_agent=body.source_agent,
        confidence=body.confidence,
    )
    store.insert(record)
    result = RecordResult(record=record, action=RecordAction.CREATED)
    return RecordResultResponse(
        record=_record_to_response(result.record),
        action=result.action.value,
        existing_id=result.existing_id,
    )


@router.get("", response_model=ExpertiseListResponse)
def list_expertise(
    domain: str | None = Query(None),
    type: str | None = Query(None),
    project: str | None = Query(None),
    tags: str | None = Query(None, description="Comma-separated tag list"),
    severity: str | None = Query(None),
    min_confidence: float | None = Query(None, ge=0.0, le=1.0),
    active_only: bool = Query(True),
    after: str | None = Query(None, description="ISO datetime"),
    agent: str | None = Query(None),
    q: str | None = Query(None, description="Text search"),
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
) -> ExpertiseListResponse:
    """Query expertise records with filters."""
    store = get_expertise_store()
    parsed_type = _parse_type(type) if type else None
    parsed_severity = _parse_severity(severity)
    parsed_tags = [t.strip() for t in tags.split(",")] if tags else None
    parsed_after: datetime | None = None
    if after:
        parsed_after = datetime.fromisoformat(after)

    query = ExpertiseQuery(
        domain=domain,
        type=parsed_type,
        project=project,
        tags=parsed_tags,
        severity=parsed_severity,
        min_confidence=min_confidence,
        active_only=active_only,
        after=parsed_after,
        agent=agent,
        q=q,
        limit=limit,
        offset=offset,
    )
    records = store.query(query)
    filters_applied: dict[str, Any] = {}
    if domain:
        filters_applied["domain"] = domain
    if type:
        filters_applied["type"] = type
    if project:
        filters_applied["project"] = project
    if tags:
        filters_applied["tags"] = tags
    if severity:
        filters_applied["severity"] = severity
    if q:
        filters_applied["q"] = q

    return ExpertiseListResponse(
        results=[_record_to_response(r) for r in records],
        total=len(records),
        filters=filters_applied,
    )


@router.get("/domains", response_model=list[DomainResponse])
def list_domains() -> list[DomainResponse]:
    """List all expertise domains with stats."""
    store = get_expertise_store()
    domains = store.list_domains()
    return [
        DomainResponse(
            name=d["name"],
            description=d.get("description"),
            record_count=d["record_count"],
            last_updated=d.get("last_updated"),
        )
        for d in domains
    ]


@router.post("/domains", status_code=201)
def create_domain(body: DomainCreateRequest) -> DomainResponse:
    """Create a new expertise domain."""
    store = get_expertise_store()
    store.create_domain(body.name, body.description)
    return DomainResponse(
        name=body.name,
        description=body.description,
        record_count=0,
        last_updated=datetime.now(timezone.utc).isoformat(),
    )


@router.get("/status", response_model=StatusResponse)
def expertise_status(project: str | None = Query(None)) -> StatusResponse:
    """Health metrics per domain."""
    store = get_expertise_store()
    config = get_config()
    all_records = store.query(ExpertiseQuery(active_only=False, limit=10000))
    if project:
        all_records = [r for r in all_records if r.project == project]

    active = [r for r in all_records if r.is_active]
    domains_set = {r.domain for r in all_records}
    domain_stats: list[dict[str, Any]] = []
    staleness_threshold = getattr(config.expertise, "staleness_threshold", 0.85)

    for d in sorted(domains_set):
        stats = store.get_domain_stats(d)
        domain_active = [r for r in active if r.domain == d]
        active_count = len(domain_active)

        # Compute staleness-based health for this domain
        stale_count = sum(
            1 for r in domain_active if compute_staleness(r) >= staleness_threshold
        )
        if stale_count == 0:
            health = "healthy"
        elif active_count > 0 and stale_count / active_count >= 0.5:
            health = "critical"
        else:
            health = "warning"

        stalest_days = 0
        if domain_active:
            now = datetime.now(timezone.utc)
            oldest_validated = min(
                r.last_validated if r.last_validated.tzinfo else r.last_validated.replace(tzinfo=timezone.utc)
                for r in domain_active
            )
            stalest_days = int((now - oldest_validated).total_seconds() / 86400)

        stats["stale_count"] = stale_count
        stats["health"] = health
        stats["stalest_record_days"] = stalest_days
        domain_stats.append(stats)

    return StatusResponse(
        total_records=len(all_records),
        active_records=len(active),
        domains=domain_stats,
    )


# ---------------------------------------------------------------------------
# Priming endpoint (must be registered before /{record_id} catch-all)
# ---------------------------------------------------------------------------


@router.get("/prime")
def prime_expertise(
    project: str | None = Query(None),
    domain: str | None = Query(None),
    max_tokens: int | None = Query(None, ge=100, le=100000),
    format: str = Query("json", description="Output format: json|markdown|prompt"),
) -> Any:
    """Token-budgeted, priority-ranked expertise priming."""
    store = get_expertise_store()
    config = get_config()

    tokens = max_tokens or config.expertise.default_prime_tokens

    query = ExpertiseQuery(
        domain=domain,
        project=project,
        active_only=True,
        limit=10000,
    )
    records = store.query(query)
    prioritizer = ExpertisePrioritizer()
    result = prioritizer.prioritize(records, max_tokens=tokens)

    formatter = PrimeFormatter()
    if format == "markdown":
        return {"content": formatter.format_markdown(result, project=project)}
    if format == "prompt":
        return {"content": formatter.format_prompt(result, project=project)}
    return formatter.format_json(result)


@router.post("/extract", response_model=ExtractionResponse)
def extract_expertise(body: ExtractionRequest) -> ExtractionResponse:
    """Run extraction pipeline on provided text."""
    from searchat.expertise.pipeline import ExtractionPipeline
    from searchat.expertise.embeddings import ExpertiseEmbeddingIndex

    store = get_expertise_store()
    config = get_config()

    embedding_index: ExpertiseEmbeddingIndex | None = None
    search_dir = store._db_path.parent.parent
    if config.expertise.enabled:
        embedding_index = ExpertiseEmbeddingIndex(
            search_dir,
            embedding_model=config.embedding.model,
        )

    pipeline = ExtractionPipeline(store, embedding_index, config)
    stats = pipeline.extract_from_text(
        body.text,
        domain=body.domain,
        project=body.project,
        conversation_id=body.conversation_id,
        mode=body.mode,
    )
    return ExtractionResponse(
        conversations_processed=stats.conversations_processed,
        records_created=stats.records_created,
        records_reinforced=stats.records_reinforced,
        records_flagged=stats.records_flagged,
        heuristic_extracted=stats.heuristic_extracted,
        llm_extracted=stats.llm_extracted,
        errors=stats.errors,
    )


# ---------------------------------------------------------------------------
# Staleness / prune endpoints (must be registered before /{record_id} catch-all)
# ---------------------------------------------------------------------------


@router.get("/stale", response_model=StaleListResponse)
def get_stale_records(
    threshold: float = Query(0.85, ge=0.0, le=1.0),
    domain: str | None = Query(None),
    project: str | None = Query(None),
    limit: int = Query(50, ge=1, le=500),
) -> StaleListResponse:
    """Return active records with staleness score >= threshold, sorted by staleness descending."""
    store = get_expertise_store()
    config = get_config()
    manager = StalenessManager(store, config)
    pairs = manager.get_stale_records(threshold=threshold)

    # Filter by domain / project
    if domain is not None:
        pairs = [(r, s) for r, s in pairs if r.domain == domain]
    if project is not None:
        pairs = [(r, s) for r, s in pairs if r.project == project]

    # Sort by staleness descending
    pairs.sort(key=lambda t: t[1], reverse=True)
    pairs = pairs[:limit]

    results = [
        StaleRecordResponse(record=_record_to_response(r), staleness_score=score)
        for r, score in pairs
    ]
    return StaleListResponse(results=results, total=len(results), threshold=threshold)


@router.post("/prune", response_model=PruneResultResponse)
def prune_expertise(body: PruneRequest) -> PruneResultResponse:
    """Soft-delete records above the staleness threshold."""
    store = get_expertise_store()
    config = get_config()
    manager = StalenessManager(store, config)
    result = manager.prune(threshold=body.threshold, dry_run=body.dry_run)
    return PruneResultResponse(
        pruned_count=len(result.pruned),
        skipped_count=len(result.skipped),
        total_evaluated=result.total_evaluated,
        dry_run=result.dry_run,
        pruned_ids=[r.id for r in result.pruned],
        skipped_ids=[r.id for r in result.skipped],
    )


@router.patch("/domains/{name}")
def patch_domain(name: str, body: DomainPatchRequest) -> DomainResponse:
    """Rename, update description, or merge a domain into another."""
    store = get_expertise_store()

    if body.merge_into is not None:
        # Move all records from `name` into `merge_into`
        records = store.query(ExpertiseQuery(domain=name, active_only=False, limit=10000))
        for record in records:
            store.update(record.id, domain=body.merge_into)
        # Update the target domain's record_count and remove the source domain
        con = store._connect()
        try:
            con.execute(
                "DELETE FROM expertise_domains WHERE name = ?",
                [name],
            )
            con.execute(
                """
                INSERT INTO expertise_domains (name, description, record_count, last_updated)
                VALUES (?, '', ?, ?)
                ON CONFLICT (name) DO UPDATE SET
                    record_count = (
                        SELECT COUNT(*) FROM expertise_records WHERE domain = excluded.name
                    ),
                    last_updated = excluded.last_updated
                """,
                [body.merge_into, len(records), datetime.now(timezone.utc)],
            )
        finally:
            con.close()
        domains = store.list_domains()
        target = next((d for d in domains if d["name"] == body.merge_into), None)
        if target is None:
            return DomainResponse(
                name=body.merge_into,
                description=None,
                record_count=len(records),
                last_updated=datetime.now(timezone.utc).isoformat(),
            )
        return DomainResponse(
            name=target["name"],
            description=target.get("description"),
            record_count=target["record_count"],
            last_updated=target.get("last_updated"),
        )

    updates: dict[str, Any] = {}
    if body.new_name is not None:
        updates["name"] = body.new_name
    if body.description is not None:
        updates["description"] = body.description

    if updates:
        con = store._connect()
        try:
            set_clauses = [f"{k} = ?" for k in updates]
            params = list(updates.values()) + [name]
            con.execute(
                f"UPDATE expertise_domains SET {', '.join(set_clauses)} WHERE name = ?",
                params,
            )
            if "name" in updates:
                con.execute(
                    "UPDATE expertise_records SET domain = ? WHERE domain = ?",
                    [updates["name"], name],
                )
        finally:
            con.close()

    effective_name = updates.get("name", name)
    domains = store.list_domains()
    target = next((d for d in domains if d["name"] == effective_name), None)
    if target is None:
        raise HTTPException(404, f"Domain not found: {effective_name}")
    return DomainResponse(
        name=target["name"],
        description=target.get("description"),
        record_count=target["record_count"],
        last_updated=target.get("last_updated"),
    )


# ---------------------------------------------------------------------------
# Record-level endpoints (parameterized routes last)
# ---------------------------------------------------------------------------


@router.get("/{record_id}", response_model=ExpertiseResponse)
def get_expertise(record_id: str) -> ExpertiseResponse:
    """Get a single expertise record by ID."""
    store = get_expertise_store()
    record = store.get(record_id)
    if record is None:
        raise HTTPException(404, f"Record not found: {record_id}")
    return _record_to_response(record)


@router.patch("/{record_id}", response_model=ExpertiseResponse)
def update_expertise(record_id: str, body: ExpertiseUpdateRequest) -> ExpertiseResponse:
    """Update fields on an existing expertise record."""
    store = get_expertise_store()
    existing = store.get(record_id)
    if existing is None:
        raise HTTPException(404, f"Record not found: {record_id}")

    updates: dict[str, Any] = {}
    if body.content is not None:
        updates["content"] = body.content
    if body.domain is not None:
        updates["domain"] = body.domain
    if body.project is not None:
        updates["project"] = body.project
    if body.severity is not None:
        updates["severity"] = _parse_severity(body.severity)
    if body.tags is not None:
        updates["tags"] = body.tags
    if body.name is not None:
        updates["name"] = body.name
    if body.example is not None:
        updates["example"] = body.example
    if body.rationale is not None:
        updates["rationale"] = body.rationale
    if body.resolution is not None:
        updates["resolution"] = body.resolution
    if body.confidence is not None:
        updates["confidence"] = body.confidence
    if body.is_active is not None:
        updates["is_active"] = body.is_active

    if updates:
        store.update(record_id, **updates)

    updated = store.get(record_id)
    if updated is None:
        raise HTTPException(404, f"Record not found after update: {record_id}")
    return _record_to_response(updated)


@router.delete("/{record_id}", status_code=200)
def delete_expertise(record_id: str) -> dict[str, str]:
    """Soft-delete an expertise record."""
    store = get_expertise_store()
    existing = store.get(record_id)
    if existing is None:
        raise HTTPException(404, f"Record not found: {record_id}")
    store.soft_delete(record_id)
    return {"status": "deleted", "id": record_id}


@router.post("/{record_id}/validate", response_model=ExpertiseResponse)
def validate_expertise(record_id: str) -> ExpertiseResponse:
    """Bump validation count and last_validated timestamp."""
    store = get_expertise_store()
    existing = store.get(record_id)
    if existing is None:
        raise HTTPException(404, f"Record not found: {record_id}")
    store.validate_record(record_id)
    updated = store.get(record_id)
    if updated is None:
        raise HTTPException(404, f"Record not found after validation: {record_id}")
    return _record_to_response(updated)
