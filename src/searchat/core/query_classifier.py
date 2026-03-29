"""Query classifier for adaptive weight selection in unified search.

Classifies queries into categories using lightweight heuristics
(regex patterns, token analysis) and maps each category to optimal
keyword/semantic fusion weights.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum


class QueryCategory(Enum):
    """Query intent categories that influence fusion weights."""
    CODE = "code"
    CONCEPTUAL = "conceptual"
    NAVIGATIONAL = "navigational"
    FACTUAL = "factual"
    SHORT = "short"


@dataclass(frozen=True)
class QueryWeights:
    """Keyword/semantic fusion weights for a classified query."""
    keyword_weight: float
    semantic_weight: float
    category: QueryCategory

    def __post_init__(self) -> None:
        total = self.keyword_weight + self.semantic_weight
        if abs(total - 1.0) > 0.01:
            raise ValueError(
                f"Weights must sum to 1.0, got {total:.3f}"
            )


# Patterns that signal code-oriented queries
_CODE_PATTERNS: list[re.Pattern[str]] = [
    re.compile(r"\b(def|class|function|import|from|return|async|await)\b"),
    re.compile(r"\b(error|exception|traceback|stack\s*trace|bug|fix)\b", re.IGNORECASE),
    re.compile(r"[A-Z][a-z]+[A-Z]"),  # camelCase / PascalCase
    re.compile(r"\w+_\w+"),  # snake_case identifiers
    re.compile(r"\.\w+\("),  # method calls like .foo(
    re.compile(r"[{}()\[\];]"),  # code punctuation
    re.compile(r"\b\w+\.\w+\.\w+\b"),  # dotted paths like os.path.join
]

# Patterns that signal navigational queries (looking for specific items)
_NAV_PATTERNS: list[re.Pattern[str]] = [
    re.compile(r"\b(where|find|locate|show|list)\b", re.IGNORECASE),
    re.compile(r"\b(file|path|directory|folder|module)\b", re.IGNORECASE),
    re.compile(r"\b(config|setting|option|flag)\b", re.IGNORECASE),
]

# Patterns that signal factual / lookup queries
_FACTUAL_PATTERNS: list[re.Pattern[str]] = [
    re.compile(r"\b(what|when|who|which|how many)\b", re.IGNORECASE),
    re.compile(r"\b(version|date|time|number|count|size)\b", re.IGNORECASE),
]

# Default weights per category
_CATEGORY_WEIGHTS: dict[QueryCategory, tuple[float, float]] = {
    QueryCategory.CODE: (0.8, 0.2),
    QueryCategory.NAVIGATIONAL: (0.7, 0.3),
    QueryCategory.FACTUAL: (0.6, 0.4),
    QueryCategory.CONCEPTUAL: (0.3, 0.7),
    QueryCategory.SHORT: (0.5, 0.5),
}


class QueryClassifier:
    """Classifies search queries and returns optimal fusion weights."""

    def __init__(
        self,
        *,
        default_keyword_weight: float = 0.6,
        default_semantic_weight: float = 0.4,
    ) -> None:
        self._default_kw = default_keyword_weight
        self._default_sem = default_semantic_weight

    def classify(self, query: str) -> QueryWeights:
        """Classify a query and return fusion weights."""
        stripped = query.strip()

        if not stripped or stripped == "*":
            return QueryWeights(
                keyword_weight=1.0,
                semantic_weight=0.0,
                category=QueryCategory.SHORT,
            )

        tokens = stripped.split()

        # Very short queries: balanced weights
        if len(tokens) <= 2 and len(stripped) < 15:
            return QueryWeights(
                keyword_weight=0.5,
                semantic_weight=0.5,
                category=QueryCategory.SHORT,
            )

        category = self._detect_category(stripped, tokens)
        kw, sem = _CATEGORY_WEIGHTS[category]
        return QueryWeights(
            keyword_weight=kw,
            semantic_weight=sem,
            category=category,
        )

    def _detect_category(self, query: str, tokens: list[str]) -> QueryCategory:
        """Detect the primary category of the query."""
        code_score = sum(1 for p in _CODE_PATTERNS if p.search(query))
        nav_score = sum(1 for p in _NAV_PATTERNS if p.search(query))
        factual_score = sum(1 for p in _FACTUAL_PATTERNS if p.search(query))

        # Code queries are distinctive — even 2 matches is strong signal
        if code_score >= 2:
            return QueryCategory.CODE

        if nav_score >= 2:
            return QueryCategory.NAVIGATIONAL

        if factual_score >= 2:
            return QueryCategory.FACTUAL

        # Longer, natural-language queries without code signals → conceptual
        if len(tokens) >= 5:
            return QueryCategory.CONCEPTUAL

        # Single strong signal
        if code_score >= 1:
            return QueryCategory.CODE
        if nav_score >= 1:
            return QueryCategory.NAVIGATIONAL
        if factual_score >= 1:
            return QueryCategory.FACTUAL

        return QueryCategory.CONCEPTUAL
