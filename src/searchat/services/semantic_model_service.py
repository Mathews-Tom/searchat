"""Service-layer builders for semantic embedding and reranking models."""
from __future__ import annotations

from typing import Any, Protocol

from searchat.config import Config


class EmbeddingModelUnavailable(RuntimeError):
    """Raised when the configured embedding model cannot be constructed."""


class RerankingModelUnavailable(RuntimeError):
    """Raised when the configured reranking model cannot be constructed."""


class EmbeddingService(Protocol):
    """Protocol for semantic embedding models."""

    def encode(self, sentences: Any, **kwargs: Any) -> Any:
        """Encode one or more sentences into embedding vectors."""


class RerankingService(Protocol):
    """Protocol for pairwise reranking models."""

    def predict(self, pairs: Any, **kwargs: Any) -> Any:
        """Score query-document pairs for reranking."""


def build_embedding_service(config: Config) -> EmbeddingService:
    """Build the configured embedding model."""
    try:
        from sentence_transformers import SentenceTransformer

        return SentenceTransformer(
            config.embedding.model,
            device=config.embedding.get_device(),
        )
    except Exception as exc:
        raise EmbeddingModelUnavailable(
            f"Embedding model unavailable: {config.embedding.model}"
        ) from exc


def build_reranking_service(config: Config) -> RerankingService:
    """Build the configured reranking model."""
    try:
        from sentence_transformers import CrossEncoder

        return CrossEncoder(config.reranking.model)
    except Exception as exc:
        raise RerankingModelUnavailable(
            f"Reranking model unavailable: {config.reranking.model}"
        ) from exc
