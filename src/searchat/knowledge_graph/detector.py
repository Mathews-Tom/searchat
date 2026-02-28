"""Contradiction detection via semantic similarity + NLI cross-encoder."""
from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from searchat.expertise.models import ExpertiseRecord
from searchat.knowledge_graph.models import ContradictionCandidate

if TYPE_CHECKING:
    from searchat.expertise.embeddings import ExpertiseEmbeddingIndex
    from searchat.expertise.store import ExpertiseStore

_logger = logging.getLogger(__name__)


class ContradictionDetector:
    """Two-stage contradiction detection: semantic similarity + NLI classification."""

    SIMILARITY_THRESHOLD: float = 0.75
    CONTRADICTION_THRESHOLD: float = 0.70
    NLI_MODEL: str = "cross-encoder/nli-deberta-v3-xsmall"

    def __init__(self, nli_model: str | None = None) -> None:
        self._nli_model_name = nli_model or self.NLI_MODEL
        self._cross_encoder = None
        self._nli_available: bool | None = None

    def _ensure_cross_encoder(self) -> bool:
        """Lazy-load the NLI cross-encoder. Returns True if available."""
        if self._nli_available is not None:
            return self._nli_available

        try:
            from sentence_transformers import CrossEncoder  # type: ignore[import]
            self._cross_encoder = CrossEncoder(self._nli_model_name)
            self._nli_available = True
        except Exception as exc:
            _logger.warning(
                "NLI cross-encoder unavailable (%s); Stage 2 skipped.", exc
            )
            self._nli_available = False

        return self._nli_available

    def _stage1_candidates(
        self,
        record: ExpertiseRecord,
        embedding_index: ExpertiseEmbeddingIndex,
        limit: int = 20,
    ) -> list[tuple[str, float]]:
        """Find semantically related records via cosine similarity."""
        results = embedding_index.search(
            record.content,
            limit=limit,
            min_similarity=self.SIMILARITY_THRESHOLD,
        )
        # Exclude the record itself
        return [(rid, score) for rid, score in results if rid != record.id]

    def _stage2_nli(
        self,
        record_a: ExpertiseRecord,
        record_b: ExpertiseRecord,
    ) -> tuple[float, float, float] | None:
        """Run NLI cross-encoder. Returns (contradiction, entailment, neutral) or None."""
        if not self._ensure_cross_encoder():
            return None
        assert self._cross_encoder is not None
        try:
            scores = self._cross_encoder.predict(
                [(record_a.content, record_b.content)]
            )
            # scores shape: (1, 3) — order depends on model label order.
            # nli-deberta-v3-xsmall: labels = [contradiction, entailment, neutral]
            score_row = scores[0] if hasattr(scores[0], "__len__") else scores
            if len(score_row) == 3:
                return float(score_row[0]), float(score_row[1]), float(score_row[2])
            return None
        except Exception as exc:
            _logger.warning("NLI prediction failed: %s", exc)
            return None

    def check_record(
        self,
        record: ExpertiseRecord,
        store: ExpertiseStore,
        embedding_index: ExpertiseEmbeddingIndex,
        limit: int = 20,
    ) -> list[ContradictionCandidate]:
        """Check a record for contradictions against the knowledge store.

        Stage 1: semantic similarity >= SIMILARITY_THRESHOLD
        Stage 2: NLI contradiction score >= CONTRADICTION_THRESHOLD (if available)
        """
        stage1 = self._stage1_candidates(record, embedding_index, limit=limit)
        if not stage1:
            return []

        nli_available = self._ensure_cross_encoder()
        candidates: list[ContradictionCandidate] = []

        for other_id, similarity in stage1:
            other = store.get(other_id)
            if other is None or not other.is_active:
                continue

            if not nli_available:
                # Stage 1 only — flag all semantically similar as candidates
                candidates.append(
                    ContradictionCandidate(
                        record_id_a=record.id,
                        record_id_b=other_id,
                        similarity_score=similarity,
                        nli_available=False,
                    )
                )
                continue

            nli_result = self._stage2_nli(record, other)
            if nli_result is None:
                candidates.append(
                    ContradictionCandidate(
                        record_id_a=record.id,
                        record_id_b=other_id,
                        similarity_score=similarity,
                        nli_available=False,
                    )
                )
                continue

            contradiction_score, entailment_score, neutral_score = nli_result
            if contradiction_score >= self.CONTRADICTION_THRESHOLD:
                candidates.append(
                    ContradictionCandidate(
                        record_id_a=record.id,
                        record_id_b=other_id,
                        similarity_score=similarity,
                        contradiction_score=contradiction_score,
                        entailment_score=entailment_score,
                        neutral_score=neutral_score,
                        nli_available=True,
                    )
                )

        return candidates
