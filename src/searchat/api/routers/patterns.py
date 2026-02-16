"""Pattern mining API endpoints."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from searchat.api.dependencies import get_config
from searchat.api.readiness import get_readiness, warming_payload, error_payload
from searchat.services.pattern_mining import extract_patterns, ExtractedPattern, PatternEvidence

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
    provider = request.model_provider.lower()
    if provider not in ("openai", "ollama", "embedded"):
        raise HTTPException(
            status_code=400,
            detail="model_provider must be 'openai', 'ollama', or 'embedded'.",
        )

    readiness = get_readiness().snapshot()
    required = ["metadata", "faiss", "embedder"]
    if provider == "embedded":
        required.append("embedded_model")

    for key in required:
        if readiness.components.get(key) == "error":
            return JSONResponse(status_code=500, content=error_payload())

    if any(readiness.components.get(key) != "ready" for key in required):
        return JSONResponse(status_code=503, content=warming_payload())

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
