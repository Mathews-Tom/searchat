from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

import searchat.api.dependencies as deps
from searchat.api.utils import parse_date_filter
from searchat.models import SearchMode
from searchat.services.tech_docs_service import build_search_filters, generate_doc


router = APIRouter()


class DocSectionRequest(BaseModel):
    name: str
    query: str
    mode: str | None = None
    filters: dict[str, Any] | None = None
    max_results: int = Field(default=10, ge=1, le=50)


class DocsSummaryRequest(BaseModel):
    title: str = "Tech Docs Summary"
    format: Literal["markdown", "asciidoc"] = "markdown"
    sections: list[DocSectionRequest] = Field(min_length=1, max_length=25)


@router.post("/docs/summary")
async def create_docs_summary(request: DocsSummaryRequest):
    config = deps.get_config()
    if not config.export.enable_tech_docs:
        raise HTTPException(status_code=404, detail="Tech docs generator is disabled")

    try:
        search_engine = deps.get_search_engine()
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    rendered_sections: list[dict[str, Any]] = []
    for section in request.sections:
        filters = section.filters or {}
        project = filters.get("project") if isinstance(filters.get("project"), str) else None
        tool = filters.get("tool") if isinstance(filters.get("tool"), str) else None

        date_str = filters.get("date") if isinstance(filters.get("date"), str) else None
        date_from_str = filters.get("date_from") if isinstance(filters.get("date_from"), str) else None
        date_to_str = filters.get("date_to") if isinstance(filters.get("date_to"), str) else None

        date_from_dt, date_to_dt = parse_date_filter(date_str, date_from_str, date_to_str)
        search_filters = build_search_filters(
            project=project,
            tool=tool,
            date_from=date_from_dt,
            date_to=date_to_dt,
        )

        mode_str = (section.mode or "hybrid").lower()
        try:
            mode = SearchMode(mode_str)
        except Exception:
            mode = SearchMode.HYBRID

        results = search_engine.search(section.query, mode=mode, filters=search_filters)
        rendered_sections.append(
            {
                "name": section.name,
                "query": section.query,
                "results": results.results[: section.max_results],
            }
        )

    doc = generate_doc(format=request.format, title=request.title, sections=rendered_sections)
    return {
        "title": request.title,
        "format": request.format,
        "generated_at": doc.generated_at,
        "content": doc.content,
        "citation_count": len(doc.citations),
        "citations": [c.__dict__ for c in doc.citations],
    }
