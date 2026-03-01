"""Pattern mining API endpoints."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from searchat.api.dependencies import get_config
from searchat.api.utils import validate_provider, check_semantic_readiness
from searchat.services.pattern_mining import extract_patterns

router = APIRouter()


class PatternExtractRequest(BaseModel):
    """Request body for pattern extraction."""

    topic: str | None = None
    max_patterns: int = Field(default=10, ge=1, le=50)
    model_provider: str = "ollama"
    model_name: str | None = None


class PatternEvidenceResponse(BaseModel):
    """Evidence item in pattern response."""

    conversation_id: str
    date: str
    snippet: str


class ExtractedPatternResponse(BaseModel):
    """Single extracted pattern in API response."""

    name: str
    description: str
    evidence: list[PatternEvidenceResponse]
    confidence: float


class PatternExtractResponse(BaseModel):
    """Response body for pattern extraction."""

    patterns: list[ExtractedPatternResponse]
    total: int


@router.post("/patterns/extract", response_model=PatternExtractResponse)
async def extract_patterns_endpoint(request: PatternExtractRequest):
    """Extract recurring patterns from conversation archives."""
    provider = validate_provider(request.model_provider)

    extra = ["embedded_model"] if provider == "embedded" else None
    not_ready = check_semantic_readiness(extra)
    if not_ready is not None:
        return not_ready

    config = get_config()

    try:
        patterns = extract_patterns(
            topic=request.topic,
            max_patterns=request.max_patterns,
            model_provider=provider,
            model_name=request.model_name,
            config=config,
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    response_patterns = [
        ExtractedPatternResponse(
            name=p.name,
            description=p.description,
            evidence=[
                PatternEvidenceResponse(
                    conversation_id=e.conversation_id,
                    date=e.date,
                    snippet=e.snippet,
                )
                for e in p.evidence
            ],
            confidence=p.confidence,
        )
        for p in patterns
    ]

    return PatternExtractResponse(patterns=response_patterns, total=len(response_patterns))
