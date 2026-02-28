"""Priming engine for L2 Expertise Store — priority ranking and formatting."""
from __future__ import annotations

from datetime import datetime, timezone

from searchat.expertise.models import ExpertiseRecord, ExpertiseSeverity, ExpertiseType, PrimeResult


class ExpertisePrioritizer:
    """Score, sort, and pack expertise records into a token budget."""

    TYPE_PRIORITY: dict[ExpertiseType, int] = {
        ExpertiseType.BOUNDARY: 100,
        ExpertiseType.FAILURE: 80,
        ExpertiseType.CONVENTION: 60,
        ExpertiseType.DECISION: 40,
        ExpertiseType.PATTERN: 30,
        ExpertiseType.INSIGHT: 10,
    }

    SEVERITY_BOOST: dict[ExpertiseSeverity, int] = {
        ExpertiseSeverity.CRITICAL: 20,
        ExpertiseSeverity.HIGH: 10,
        ExpertiseSeverity.MEDIUM: 0,
        ExpertiseSeverity.LOW: -20,
    }

    def _recency_boost(self, last_validated: datetime) -> int:
        now = datetime.now(timezone.utc)
        delta_days = (now - last_validated).days
        if delta_days <= 7:
            return 5
        if delta_days <= 30:
            return 3
        if delta_days <= 90:
            return 1
        return 0

    def _score(self, record: ExpertiseRecord) -> float:
        score = float(self.TYPE_PRIORITY[record.type])
        if record.severity is not None:
            score += self.SEVERITY_BOOST[record.severity]
        score += min(record.validation_count * 2, 20)
        score += record.confidence * 10
        score += self._recency_boost(record.last_validated)
        return score

    def _count_tokens(self, record: ExpertiseRecord) -> int:
        return int(len(record.content.split()) * 1.3)

    def prioritize(self, records: list[ExpertiseRecord], max_tokens: int = 4000) -> PrimeResult:
        active = [r for r in records if r.is_active]
        filtered_inactive = len(records) - len(active)

        scored = sorted(active, key=self._score, reverse=True)

        packed: list[ExpertiseRecord] = []
        token_total = 0
        for record in scored:
            tokens = self._count_tokens(record)
            if token_total + tokens > max_tokens:
                continue
            packed.append(record)
            token_total += tokens

        domains_covered = sorted({r.domain for r in packed})

        return PrimeResult(
            expertise=packed,
            token_count=token_total,
            domains_covered=domains_covered,
            records_total=len(records),
            records_included=len(packed),
            records_filtered_inactive=filtered_inactive,
        )


class PrimeFormatter:
    """Format PrimeResult into various output representations."""

    _TYPE_LABEL: dict[ExpertiseType, str] = {
        ExpertiseType.BOUNDARY: "Boundaries",
        ExpertiseType.FAILURE: "Known Failures",
        ExpertiseType.CONVENTION: "Conventions",
        ExpertiseType.DECISION: "Decisions",
        ExpertiseType.PATTERN: "Patterns",
        ExpertiseType.INSIGHT: "Insights",
    }

    _TYPE_PREFIX: dict[ExpertiseType, str] = {
        ExpertiseType.BOUNDARY: "BOUNDARY",
        ExpertiseType.FAILURE: "FAILURE",
        ExpertiseType.CONVENTION: "CONVENTION",
        ExpertiseType.DECISION: "DECISION",
        ExpertiseType.PATTERN: "PATTERN",
        ExpertiseType.INSIGHT: "INSIGHT",
    }

    def format_markdown(self, result: PrimeResult, project: str | None = None) -> str:
        header = f"## Project Expertise ({project})" if project else "## Project Expertise"
        lines: list[str] = [header, ""]

        by_type: dict[ExpertiseType, list[ExpertiseRecord]] = {}
        for record in result.expertise:
            by_type.setdefault(record.type, []).append(record)

        type_order = [
            ExpertiseType.BOUNDARY,
            ExpertiseType.FAILURE,
            ExpertiseType.CONVENTION,
            ExpertiseType.DECISION,
            ExpertiseType.PATTERN,
            ExpertiseType.INSIGHT,
        ]

        for etype in type_order:
            records = by_type.get(etype)
            if not records:
                continue
            lines.append(f"### {self._TYPE_LABEL[etype]}")
            for r in records:
                if etype == ExpertiseType.BOUNDARY:
                    lines.append(f"- **{r.content}**")
                elif etype == ExpertiseType.CONVENTION:
                    lines.append(f"- {r.content}")
                elif etype == ExpertiseType.DECISION:
                    entry = f"- **{r.name or r.content}**"
                    if r.rationale:
                        entry += f": {r.rationale}"
                    lines.append(entry)
                elif etype == ExpertiseType.FAILURE:
                    entry = f"- \u26a0\ufe0f {r.content}"
                    if r.resolution:
                        entry += f" — {r.resolution}"
                    lines.append(entry)
                else:
                    lines.append(f"- {r.content}")
            lines.append("")

        return "\n".join(lines).rstrip() + "\n"

    def format_json(self, result: PrimeResult) -> dict:
        def _serialize_record(r: ExpertiseRecord) -> dict:
            return {
                "id": r.id,
                "type": r.type.value,
                "domain": r.domain,
                "content": r.content,
                "project": r.project,
                "confidence": r.confidence,
                "source_conversation_id": r.source_conversation_id,
                "source_agent": r.source_agent,
                "tags": r.tags,
                "severity": r.severity.value if r.severity else None,
                "created_at": r.created_at.isoformat(),
                "last_validated": r.last_validated.isoformat(),
                "validation_count": r.validation_count,
                "is_active": r.is_active,
                "name": r.name,
                "example": r.example,
                "rationale": r.rationale,
                "alternatives_considered": r.alternatives_considered,
                "resolution": r.resolution,
            }

        return {
            "expertise": [_serialize_record(r) for r in result.expertise],
            "token_count": result.token_count,
            "domains_covered": result.domains_covered,
            "records_total": result.records_total,
            "records_included": result.records_included,
            "records_filtered_inactive": result.records_filtered_inactive,
        }

    def format_prompt(self, result: PrimeResult, project: str | None = None) -> str:
        lines: list[str] = []
        if project:
            lines.append(f"Project expertise for: {project}")
            lines.append("")

        for i, r in enumerate(result.expertise, start=1):
            prefix = self._TYPE_PREFIX[r.type]
            if r.type == ExpertiseType.FAILURE and r.resolution:
                entry = f"{i}. [{prefix}] {r.content} Fix: {r.resolution}"
            elif r.type == ExpertiseType.DECISION and r.rationale:
                entry = f"{i}. [{prefix}] {r.name or r.content}: {r.rationale}"
            else:
                entry = f"{i}. [{prefix}] {r.content}"
            lines.append(entry)

        return "\n".join(lines)
