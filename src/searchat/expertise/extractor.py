"""Heuristic extractor — regex-based signal detection for expertise records."""
from __future__ import annotations

import re
from dataclasses import dataclass

from searchat.expertise.models import ExpertiseRecord, ExpertiseSeverity, ExpertiseType


@dataclass(frozen=True)
class _Signal:
    """A signal pattern that maps a regex to an expertise type."""

    pattern: re.Pattern[str]
    type: ExpertiseType
    confidence: float


# Strong signals get 0.5 confidence, weak signals get 0.3.
_SIGNALS: list[_Signal] = [
    # Convention signals
    _Signal(re.compile(r"always use\b", re.IGNORECASE), ExpertiseType.CONVENTION, 0.5),
    _Signal(re.compile(r"never do\b", re.IGNORECASE), ExpertiseType.CONVENTION, 0.5),
    _Signal(re.compile(r"the convention is\b", re.IGNORECASE), ExpertiseType.CONVENTION, 0.5),
    _Signal(re.compile(r"we standardize on\b", re.IGNORECASE), ExpertiseType.CONVENTION, 0.5),
    _Signal(re.compile(r"rule of thumb\b", re.IGNORECASE), ExpertiseType.CONVENTION, 0.4),
    _Signal(re.compile(r"standard practice\b", re.IGNORECASE), ExpertiseType.CONVENTION, 0.4),
    # Pattern signals
    _Signal(re.compile(r"the pattern is\b", re.IGNORECASE), ExpertiseType.PATTERN, 0.5),
    _Signal(re.compile(r"the approach we use\b", re.IGNORECASE), ExpertiseType.PATTERN, 0.5),
    _Signal(re.compile(r"the standard way\b", re.IGNORECASE), ExpertiseType.PATTERN, 0.5),
    _Signal(re.compile(r"template for\b", re.IGNORECASE), ExpertiseType.PATTERN, 0.4),
    # Failure signals
    _Signal(re.compile(r"the fix was\b", re.IGNORECASE), ExpertiseType.FAILURE, 0.5),
    _Signal(re.compile(r"root cause\b", re.IGNORECASE), ExpertiseType.FAILURE, 0.5),
    _Signal(re.compile(r"the bug was\b", re.IGNORECASE), ExpertiseType.FAILURE, 0.5),
    _Signal(re.compile(r"the issue was caused by\b", re.IGNORECASE), ExpertiseType.FAILURE, 0.5),
    _Signal(re.compile(r"lesson learned\b", re.IGNORECASE), ExpertiseType.FAILURE, 0.4),
    # Decision signals
    _Signal(re.compile(r"we decided to\b", re.IGNORECASE), ExpertiseType.DECISION, 0.5),
    _Signal(re.compile(r"we chose\b", re.IGNORECASE), ExpertiseType.DECISION, 0.5),
    _Signal(re.compile(r"the rationale is\b", re.IGNORECASE), ExpertiseType.DECISION, 0.5),
    _Signal(re.compile(r"we went with .+ over\b", re.IGNORECASE), ExpertiseType.DECISION, 0.5),
    # Boundary signals
    _Signal(re.compile(r"must not\b", re.IGNORECASE), ExpertiseType.BOUNDARY, 0.4),
    _Signal(re.compile(r"hard requirement\b", re.IGNORECASE), ExpertiseType.BOUNDARY, 0.5),
    _Signal(re.compile(r"non-negotiable\b", re.IGNORECASE), ExpertiseType.BOUNDARY, 0.5),
    _Signal(re.compile(r"always ensure\b", re.IGNORECASE), ExpertiseType.BOUNDARY, 0.4),
    # Insight signals
    _Signal(re.compile(r"interesting finding\b", re.IGNORECASE), ExpertiseType.INSIGHT, 0.4),
    _Signal(re.compile(r"I noticed that\b", re.IGNORECASE), ExpertiseType.INSIGHT, 0.3),
    _Signal(re.compile(r"worth noting\b", re.IGNORECASE), ExpertiseType.INSIGHT, 0.4),
    _Signal(re.compile(r"observation\b", re.IGNORECASE), ExpertiseType.INSIGHT, 0.3),
]

# Sentence boundary: period/question/exclamation followed by whitespace or end,
# or newline boundaries.
_SENTENCE_SPLIT = re.compile(r"(?<=[.!?])\s+|\n{2,}")


def _extract_sentence(text: str, match_start: int, match_end: int) -> str:
    """Extract the sentence (or paragraph) containing the match position."""
    # Find sentence boundaries around the match
    sentences = _SENTENCE_SPLIT.split(text)
    pos = 0
    for sentence in sentences:
        sent_start = text.find(sentence, pos)
        if sent_start == -1:
            pos += len(sentence)
            continue
        sent_end = sent_start + len(sentence)
        if sent_start <= match_start < sent_end:
            return sentence.strip()
        pos = sent_end

    # Fallback: return a window around the match
    window_start = max(0, match_start - 100)
    window_end = min(len(text), match_end + 200)
    return text[window_start:window_end].strip()


class HeuristicExtractor:
    """Extract expertise records from text using regex signal detection.

    Confidence range: 0.3–0.5 (well below LLM-based extraction).
    Precision: 40-70%, recall: 30-50% (structural ceiling for regex).
    """

    def extract(
        self,
        text: str,
        domain: str = "general",
        project: str | None = None,
    ) -> list[ExpertiseRecord]:
        """Scan text for signal patterns and produce expertise records."""
        if not text or not text.strip():
            return []

        records: list[ExpertiseRecord] = []
        seen_content: set[str] = set()

        for signal in _SIGNALS:
            for match in signal.pattern.finditer(text):
                content = _extract_sentence(text, match.start(), match.end())
                if not content or len(content) < 10:
                    continue

                # Deduplicate within this extraction run
                content_key = content[:100].lower()
                if content_key in seen_content:
                    continue
                seen_content.add(content_key)

                severity: ExpertiseSeverity | None = None
                if signal.type in (ExpertiseType.FAILURE, ExpertiseType.BOUNDARY):
                    severity = ExpertiseSeverity.MEDIUM

                records.append(
                    ExpertiseRecord(
                        type=signal.type,
                        domain=domain,
                        content=content,
                        project=project,
                        confidence=signal.confidence,
                        source_agent="heuristic-extractor",
                        severity=severity,
                    )
                )

        return records
