"""Pattern mining service for extracting recurring patterns from conversation archives."""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass

from searchat.api.dependencies import get_search_engine
from searchat.config import Config
from searchat.config.constants import PATTERN_MINING_SEEDS
from searchat.models import SearchMode, SearchFilters
from searchat.services.llm_service import LLMService

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class PatternEvidence:
    """Evidence supporting an extracted pattern."""

    conversation_id: str
    date: str
    snippet: str


@dataclass(frozen=True)
class ExtractedPattern:
    """A pattern extracted from conversation history."""

    name: str
    description: str
    evidence: list[PatternEvidence]
    confidence: float


def extract_patterns(
    *,
    topic: str | None = None,
    max_patterns: int = 10,
    model_provider: str = "ollama",
    model_name: str | None = None,
    config: Config,
) -> list[ExtractedPattern]:
    """Extract recurring patterns from conversation history.

    Algorithm:
    1. Generate seed queries from topic or defaults
    2. Run hybrid search for each seed
    3. Deduplicate results by conversation_id
    4. Cluster results by semantic similarity
    5. Synthesize patterns via RAG for each cluster

    Args:
        topic: Optional topic to focus pattern extraction on.
        max_patterns: Maximum number of patterns to return.
        model_provider: LLM provider for synthesis.
        model_name: Optional specific model name.
        config: Application config.

    Returns:
        List of extracted patterns with evidence.
    """
    search_engine = get_search_engine()

    # Step 1: Generate seed queries
    if topic:
        seeds = [
            f"{topic} conventions",
            f"{topic} patterns",
            f"{topic} best practices",
        ]
    else:
        seeds = list(PATTERN_MINING_SEEDS)

    # Step 2: Collect search results from all seeds
    all_results: dict[str, tuple[object, str]] = {}  # conv_id -> (result, seed)
    for seed in seeds:
        results = search_engine.search(seed, mode=SearchMode.HYBRID, filters=SearchFilters())
        for r in results.results[:20]:
            if r.conversation_id not in all_results:
                all_results[r.conversation_id] = (r, seed)

    if not all_results:
        return []

    # Step 3: Group results into clusters (simple approach: chunk by seed affinity)
    seed_clusters: dict[str, list[object]] = {}
    for conv_id, (result, seed) in all_results.items():
        seed_clusters.setdefault(seed, []).append(result)

    # Step 4: For each cluster, synthesize a pattern via LLM
    llm = LLMService(config.llm)
    patterns: list[ExtractedPattern] = []

    for seed, cluster_results in list(seed_clusters.items())[:max_patterns]:
        # Build context from cluster
        context_lines: list[str] = []
        evidence_items: list[PatternEvidence] = []
        for r in cluster_results[:5]:  # Cap at 5 per cluster
            context_lines.append(
                f"Source: {r.conversation_id}\n"
                f"Date: {r.updated_at.isoformat()}\n"
                f"Project: {r.project_id}\n"
                f"Snippet: {r.snippet}\n"
            )
            evidence_items.append(
                PatternEvidence(
                    conversation_id=r.conversation_id,
                    date=r.updated_at.isoformat(),
                    snippet=r.snippet,
                )
            )

        context = "\n---\n".join(context_lines)
        synthesis_prompt = (
            "Analyze these conversation excerpts and identify a specific pattern, "
            "convention, or rule that appears across them. Output valid JSON only:\n"
            '{"name": "...", "description": "...", "confidence": 0.0-1.0}\n\n'
            f"Excerpts:\n{context}"
        )

        messages = [
            {"role": "system", "content": "You extract development patterns from conversation archives. Output valid JSON only."},
            {"role": "user", "content": synthesis_prompt},
        ]

        try:
            response = llm.completion(
                messages=messages,
                provider=model_provider,
                model_name=model_name,
            )
            parsed = json.loads(response.strip())
            patterns.append(
                ExtractedPattern(
                    name=parsed.get("name", seed),
                    description=parsed.get("description", ""),
                    evidence=evidence_items,
                    confidence=float(parsed.get("confidence", 0.5)),
                )
            )
        except (json.JSONDecodeError, KeyError, ValueError) as exc:
            logger.warning("Failed to parse pattern from LLM response for seed '%s': %s", seed, exc)
            patterns.append(
                ExtractedPattern(
                    name=seed,
                    description=f"Pattern cluster related to: {seed}",
                    evidence=evidence_items,
                    confidence=0.3,
                )
            )

    return patterns[:max_patterns]
