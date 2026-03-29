"""Progressive fallback for degraded-mode search resilience.

Provides a 3-tier fallback chain:
  Tier 1 — Full hybrid (keyword + semantic + fusion)
  Tier 2 — Keyword only (if semantic is unavailable)
  Tier 3 — Wildcard browse (if keyword FTS also fails)

The UnifiedSearchEngine delegates to this component when
a search tier raises an exception.
"""
from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import dataclass, field

from searchat.models.domain import SearchResult

log = logging.getLogger(__name__)


@dataclass
class FallbackResult:
    """Outcome of a progressive fallback search."""
    results: list[SearchResult]
    tier_used: int
    mode_used: str
    errors: list[str] = field(default_factory=list)


# Type alias for a search tier callable: () -> list[SearchResult]
SearchTier = Callable[[], list[SearchResult]]


class ProgressiveFallback:
    """Execute search tiers in order, falling back on failure."""

    def execute(
        self,
        tiers: list[tuple[str, SearchTier]],
    ) -> FallbackResult:
        """Try each (mode_name, callable) tier in order.

        Returns the result of the first successful tier.
        If all tiers fail, returns an empty result with all errors collected.
        """
        errors: list[str] = []

        for tier_num, (mode_name, search_fn) in enumerate(tiers, start=1):
            try:
                results = search_fn()
                return FallbackResult(
                    results=results,
                    tier_used=tier_num,
                    mode_used=mode_name,
                    errors=errors,
                )
            except Exception as exc:
                msg = f"Tier {tier_num} ({mode_name}) failed: {exc}"
                log.warning(msg)
                errors.append(msg)

        # All tiers exhausted
        return FallbackResult(
            results=[],
            tier_used=0,
            mode_used="none",
            errors=errors,
        )
