from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

import searchat.api.dependencies as deps
from searchat.api.utils import parse_date_filter
from searchat.config.constants import AGENT_CONFIG_TEMPLATES
from searchat.models import SearchMode
from searchat.services.pattern_mining import extract_patterns
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


class AgentConfigRequest(BaseModel):
    """Request body for agent config generation."""

    format: Literal["claude.md", "copilot-instructions.md", "cursorrules"] = "claude.md"
    project_filter: str | None = None
    model_provider: str = "ollama"
    model_name: str | None = None


@router.post("/export/agent-config")
async def generate_agent_config(request: AgentConfigRequest):
    """Generate agent configuration from conversation patterns."""
    provider = request.model_provider.lower()
    if provider not in ("openai", "ollama", "embedded"):
        raise HTTPException(
            status_code=400,
            detail="model_provider must be 'openai', 'ollama', or 'embedded'.",
        )

    config = deps.get_config()

    try:
        patterns = extract_patterns(
            topic=request.project_filter,
            max_patterns=15,
            model_provider=provider,
            model_name=request.model_name,
            config=config,
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    # Format patterns into text
    pattern_lines: list[str] = []
    for p in patterns:
        pattern_lines.append(f"### {p.name}")
        pattern_lines.append(f"{p.description}")
        if p.evidence:
            pattern_lines.append("")
            pattern_lines.append("Evidence:")
            for e in p.evidence[:3]:
                pattern_lines.append(f"- [{e.date}] {e.snippet[:100]}...")
        pattern_lines.append("")

    patterns_text = "\n".join(pattern_lines)
    project_name = request.project_filter or "Project"

    template = AGENT_CONFIG_TEMPLATES.get(request.format, AGENT_CONFIG_TEMPLATES["claude.md"])
    content = template.format(project_name=project_name, patterns=patterns_text)

    return {
        "format": request.format,
        "content": content,
        "pattern_count": len(patterns),
        "project_filter": request.project_filter,
    }
