from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Literal

from searchat.models import SearchFilters, SearchMode, SearchResult


DocFormat = Literal["markdown", "asciidoc"]


@dataclass(frozen=True)
class DocCitation:
    conversation_id: str
    title: str
    project_id: str
    tool: str
    message_start_index: int | None
    message_end_index: int | None


@dataclass(frozen=True)
class GeneratedDoc:
    content: str
    citations: list[DocCitation]
    generated_at: str


def build_search_filters(*, project: str | None, tool: str | None, date_from: datetime | None, date_to: datetime | None) -> SearchFilters:
    return SearchFilters(
        project_ids=[project] if project else None,
        tool=tool or None,
        date_from=date_from,
        date_to=date_to,
    )


def generate_doc(
    *,
    format: DocFormat,
    title: str,
    sections: list[dict[str, Any]],
) -> GeneratedDoc:
    # sections: [{name, query, results: list[SearchResult]}]
    now = datetime.utcnow().isoformat()
    citations: list[DocCitation] = []

    if format == "markdown":
        content = _render_markdown(title=title, sections=sections, citations=citations)
    else:
        content = _render_asciidoc(title=title, sections=sections, citations=citations)

    return GeneratedDoc(content=content, citations=citations, generated_at=now)


def _render_markdown(*, title: str, sections: list[dict[str, Any]], citations: list[DocCitation]) -> str:
    lines: list[str] = [f"# {title}", ""]
    lines.append("## Table of Contents")
    for section in sections:
        anchor = _md_anchor(section["name"])
        lines.append(f"- [{section['name']}](#{anchor})")
    lines.append("")

    for section in sections:
        lines.append(f"## {section['name']}")
        if section.get("query"):
            lines.append(f"_Query:_ `{section['query']}`")
            lines.append("")

        results: list[SearchResult] = section.get("results", [])
        grouped = _group_results(results)
        for group_name, group_results in grouped.items():
            lines.append(f"### {group_name}")
            for r in group_results:
                rng = _format_range(r.message_start_index, r.message_end_index)
                lines.append(f"- {r.title} (`{r.conversation_id}`{rng})")
                snippet = (r.snippet or "").strip()
                if snippet:
                    lines.append(f"  - {snippet}")

                citations.append(
                    DocCitation(
                        conversation_id=r.conversation_id,
                        title=r.title,
                        project_id=r.project_id,
                        tool=_detect_tool(r),
                        message_start_index=r.message_start_index,
                        message_end_index=r.message_end_index,
                    )
                )
            lines.append("")

    lines.append("## References")
    for c in citations:
        rng = _format_range(c.message_start_index, c.message_end_index)
        lines.append(f"- {c.title} (`{c.conversation_id}`) [{c.tool} / {c.project_id}]{rng}")
    lines.append("")
    return "\n".join(lines)


def _render_asciidoc(*, title: str, sections: list[dict[str, Any]], citations: list[DocCitation]) -> str:
    lines: list[str] = [f"= {title}", ":toc:", ":toclevels: 2", ""]

    for section in sections:
        lines.append(f"== {section['name']}")
        if section.get("query"):
            lines.append(f"Query: `{section['query']}`")
            lines.append("")

        results: list[SearchResult] = section.get("results", [])
        grouped = _group_results(results)
        for group_name, group_results in grouped.items():
            lines.append(f"=== {group_name}")
            for r in group_results:
                rng = _format_range(r.message_start_index, r.message_end_index)
                lines.append(f"* {r.title} (`{r.conversation_id}`{rng})")
                snippet = (r.snippet or "").strip()
                if snippet:
                    lines.append(f"** {snippet}")

                citations.append(
                    DocCitation(
                        conversation_id=r.conversation_id,
                        title=r.title,
                        project_id=r.project_id,
                        tool=_detect_tool(r),
                        message_start_index=r.message_start_index,
                        message_end_index=r.message_end_index,
                    )
                )
            lines.append("")

    lines.append("== References")
    for c in citations:
        rng = _format_range(c.message_start_index, c.message_end_index)
        lines.append(f"* {c.title} (`{c.conversation_id}`) [{c.tool} / {c.project_id}]{rng}")
    lines.append("")
    return "\n".join(lines)


def _group_results(results: list[SearchResult]) -> dict[str, list[SearchResult]]:
    grouped: dict[str, list[SearchResult]] = {}
    for r in results:
        tool = _detect_tool(r)
        key = f"{tool} / {r.project_id}"
        grouped.setdefault(key, []).append(r)
    return grouped


def _detect_tool(result: SearchResult) -> str:
    path = (result.file_path or "").lower()
    if "/.vibe/" in path:
        return "vibe"
    if "/opencode/" in path or "/.local/share/opencode/" in path:
        return "opencode"
    if "/.claude/" in path:
        return "claude"
    return "unknown"


def _md_anchor(text: str) -> str:
    return "-".join("".join(ch.lower() if ch.isalnum() else " " for ch in text).split())


def _format_range(start: int | None, end: int | None) -> str:
    if start is None or end is None:
        return ""
    return f" messages {start}-{end}"
