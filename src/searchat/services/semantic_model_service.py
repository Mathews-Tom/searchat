"""Service-layer builders for semantic embedding and reranking models."""
from __future__ import annotations

from typing import Any, Protocol

from searchat.config import Config


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
    from sentence_transformers import SentenceTransformer

    return SentenceTransformer(
        config.embedding.model,
        device=config.embedding.get_device(),
    )


def build_reranking_service(config: Config) -> RerankingService:
    """Build the configured reranking model."""
    from sentence_transformers import CrossEncoder

    return CrossEncoder(config.reranking.model)
