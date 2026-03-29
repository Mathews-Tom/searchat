"""CombMNZ result fusion with percentile normalization.

Merges keyword (BM25) and semantic (vector) result lists into a
unified ranked list using CombMNZ — results appearing in both lists
receive a multiplicative intersection boost.
"""
from __future__ import annotations

from dataclasses import dataclass

from searchat.models.domain import SearchResult


@dataclass(frozen=True)
class MergeConfig:
    """Parameters controlling fusion behavior."""
    keyword_weight: float = 0.6
    semantic_weight: float = 0.4
    intersection_boost: float = 1.5
    max_results: int = 100


class ResultMerger:
    """CombMNZ fusion with percentile-rank normalization."""

    def __init__(self, config: MergeConfig | None = None) -> None:
        self._config = config or MergeConfig()

    def merge(
        self,
        keyword_results: list[SearchResult],
        semantic_results: list[SearchResult],
        *,
        keyword_weight: float | None = None,
        semantic_weight: float | None = None,
    ) -> list[SearchResult]:
        """Merge two ranked lists using CombMNZ fusion.

        Returns a fused list sorted by combined score, capped at max_results.
        Each result's .score is updated to the fused score.  .bm25_score and
        .semantic_score are set to their respective normalized values.
        """
        kw = keyword_weight if keyword_weight is not None else self._config.keyword_weight
        sw = semantic_weight if semantic_weight is not None else self._config.semantic_weight
        boost = self._config.intersection_boost
        max_n = self._config.max_results

        # Build percentile-normalized score maps
        kw_scores = _percentile_normalize(keyword_results)
        sem_scores = _percentile_normalize(semantic_results)

        # Collect all conversation IDs and best result objects
        result_map: dict[str, SearchResult] = {}
        for r in keyword_results:
            result_map[r.conversation_id] = r
        for r in semantic_results:
            if r.conversation_id not in result_map:
                result_map[r.conversation_id] = r

        # CombMNZ: sum of weighted normalized scores × count of lists present
        fused: dict[str, float] = {}
        for cid in result_map:
            kw_score = kw_scores.get(cid, 0.0)
            sem_score = sem_scores.get(cid, 0.0)

            weighted_sum = kw_score * kw + sem_score * sw

            # Count how many lists this result appears in
            list_count = (1 if cid in kw_scores else 0) + (1 if cid in sem_scores else 0)

            # CombMNZ: multiply by list count, then apply intersection boost
            if list_count == 2:
                fused[cid] = weighted_sum * list_count * boost
            else:
                fused[cid] = weighted_sum * list_count

            # Store component scores on the result
            result = result_map[cid]
            result.bm25_score = kw_score
            result.semantic_score = sem_score

        # Sort by fused score descending
        ranked = sorted(fused.items(), key=lambda x: x[1], reverse=True)

        out: list[SearchResult] = []
        for cid, score in ranked[:max_n]:
            result = result_map[cid]
            result.score = score
            out.append(result)

        return out


def _percentile_normalize(results: list[SearchResult]) -> dict[str, float]:
    """Percentile-rank normalization: rank / N → [0, 1].

    Rank 1 (best) gets score 1.0, last rank gets score 1/N.
    """
    if not results:
        return {}

    n = len(results)
    return {
        r.conversation_id: (n - rank) / n
        for rank, r in enumerate(results)
    }
