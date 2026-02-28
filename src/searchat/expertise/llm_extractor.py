"""LLM-powered expertise extractor."""
from __future__ import annotations

import json

from searchat.config.settings import LLMConfig
from searchat.expertise.models import (
    ExpertiseRecord,
    ExpertiseSeverity,
    ExpertiseType,
)
from searchat.services.llm_service import LLMService, LLMServiceError

EXTRACTION_PROMPT = """\
Analyze this AI coding conversation and extract structured expertise records.
For each piece of knowledge worth preserving, output a JSON object with:
- type: one of [convention, pattern, failure, decision, boundary, insight]
- domain: the technical domain (e.g., database, auth, api, testing, deployment)
- content: the knowledge itself, written as a clear, standalone statement
- confidence: how confident you are this is accurate (0.0-1.0)
- severity: for failures/boundaries only (low, medium, high, critical)
Rules:
- Only extract knowledge that would be useful in future sessions
- Skip trivial observations or project-specific implementation details
- Each record should be self-contained
- Prefer actionable statements over observations
- If a failure was resolved, include both the problem and the resolution
Output as a JSON array. If nothing worth extracting, return []."""

_CONFIDENCE_MIN = 0.7
_CONFIDENCE_MAX = 0.9


class ExtractionError(RuntimeError):
    """Raised when extraction fails (LLM unavailable, bad response, etc.)."""


class LLMExtractor:
    """Extracts ExpertiseRecord objects from conversation text using an LLM."""

    def __init__(
        self,
        llm_config: LLMConfig,
        provider: str | None = None,
        model: str | None = None,
    ) -> None:
        self._llm = LLMService(llm_config)
        self._provider = provider or llm_config.default_provider
        self._model = model

    def extract(
        self,
        text: str,
        domain: str = "general",
        project: str | None = None,
    ) -> list[ExpertiseRecord]:
        """Send conversation text to LLM and return parsed ExpertiseRecord list."""
        messages = [
            {"role": "system", "content": EXTRACTION_PROMPT},
            {"role": "user", "content": text},
        ]
        try:
            raw = self._llm.completion(
                messages=messages,
                provider=self._provider,
                model_name=self._model,
                temperature=0.2,
            )
        except LLMServiceError as exc:
            raise ExtractionError(
                f"LLM provider '{self._provider}' unavailable: {exc}. "
                "Ensure the provider is configured and reachable."
            ) from exc

        try:
            items: list[dict] = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise ExtractionError(
                f"LLM returned non-JSON response: {exc}\nRaw output: {raw!r}"
            ) from exc

        if not isinstance(items, list):
            raise ExtractionError(
                f"LLM response must be a JSON array, got {type(items).__name__!r}."
            )

        records: list[ExpertiseRecord] = []
        for item in items:
            record = self._build_record(item, domain, project)
            records.append(record)
        return records

    def extract_batch(
        self,
        texts: list[tuple[str, str, str | None]],
        batch_size: int = 5,
    ) -> list[ExpertiseRecord]:
        """Process multiple (text, domain, project) tuples sequentially."""
        results: list[ExpertiseRecord] = []
        for i in range(0, len(texts), batch_size):
            batch = texts[i : i + batch_size]
            for text, domain, project in batch:
                records = self.extract(text, domain=domain, project=project)
                results.extend(records)
        return results

    def _build_record(
        self,
        item: dict,
        fallback_domain: str,
        project: str | None,
    ) -> ExpertiseRecord:
        try:
            raw_type = item["type"]
            expertise_type = ExpertiseType(raw_type)
        except (KeyError, ValueError) as exc:
            raise ExtractionError(
                f"Invalid or missing 'type' in LLM item: {item!r}"
            ) from exc

        content = item.get("content")
        if not content or not isinstance(content, str):
            raise ExtractionError(
                f"Missing or invalid 'content' in LLM item: {item!r}"
            )

        domain = item.get("domain") or fallback_domain

        raw_confidence = item.get("confidence", 0.8)
        try:
            confidence = float(raw_confidence)
        except (TypeError, ValueError):
            confidence = 0.8
        confidence = max(_CONFIDENCE_MIN, min(_CONFIDENCE_MAX, confidence))

        severity: ExpertiseSeverity | None = None
        if "severity" in item and item["severity"]:
            try:
                severity = ExpertiseSeverity(item["severity"])
            except ValueError:
                severity = None

        return ExpertiseRecord(
            type=expertise_type,
            domain=domain,
            content=content,
            project=project,
            confidence=confidence,
            source_agent="llm-extractor",
            severity=severity,
        )
