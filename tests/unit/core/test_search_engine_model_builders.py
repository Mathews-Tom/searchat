from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pytest

from searchat.config import Config
from searchat.config.constants import (
    INDEX_FORMAT,
    INDEX_FORMAT_VERSION,
    INDEX_METADATA_FILENAME,
    INDEX_SCHEMA_VERSION,
)
from searchat.core.search_engine import SearchEngine
from searchat.models import SearchFilters, SearchMode, SearchResult
from searchat.services.retrieval_service import SemanticSearchUnavailable
from searchat.services.semantic_model_service import (
    EmbeddingModelUnavailable,
    RerankingModelUnavailable,
)


def _prepare_search_dir(search_dir: Path, cfg: Config) -> None:
    conversations = search_dir / "data" / "conversations"
    conversations.mkdir(parents=True, exist_ok=True)
    (conversations / "c.parquet").write_bytes(b"")

    indices = search_dir / "data" / "indices"
    indices.mkdir(parents=True, exist_ok=True)
    (indices / "embeddings.metadata.parquet").write_bytes(b"")
    (indices / "embeddings.faiss").write_bytes(b"")
    (indices / INDEX_METADATA_FILENAME).write_text(
        json.dumps(
            {
                "embedding_model": cfg.embedding.model,
                "format": INDEX_FORMAT,
                "schema_version": INDEX_SCHEMA_VERSION,
                "index_format_version": INDEX_FORMAT_VERSION,
            }
        ),
        encoding="utf-8",
    )


@pytest.mark.unit
def test_search_engine_uses_embedding_builder(monkeypatch: pytest.MonkeyPatch, temp_search_dir: Path):
    cfg = Config.load()
    _prepare_search_dir(temp_search_dir, cfg)

    built = object()
    calls: list[object] = []

    def _fake_build_embedding_service(config):
        calls.append(config)
        return built

    monkeypatch.setattr(
        "searchat.core.search_engine.build_embedding_service",
        _fake_build_embedding_service,
    )

    engine = SearchEngine(temp_search_dir, cfg)
    engine.ensure_embedder_loaded()
    engine.ensure_embedder_loaded()

    assert engine.embedder is built
    assert calls == [cfg]


@pytest.mark.unit
def test_search_engine_rerank_uses_reranker_builder(monkeypatch: pytest.MonkeyPatch, temp_search_dir: Path):
    cfg = Config.load()
    cfg.reranking.enabled = True
    cfg.reranking.top_k = 2
    _prepare_search_dir(temp_search_dir, cfg)

    calls: list[object] = []

    class _Reranker:
        def predict(self, pairs):
            calls.append(pairs)
            return [0.2, 0.9]

    monkeypatch.setattr(
        "searchat.core.search_engine.build_reranking_service",
        lambda _config: _Reranker(),
    )

    engine = SearchEngine(temp_search_dir, cfg)
    now = datetime.now(timezone.utc)
    results = [
        SearchResult(
            conversation_id="conv-1",
            project_id="p",
            title="Title 1",
            created_at=now,
            updated_at=now,
            message_count=1,
            file_path="/tmp/1.jsonl",
            score=0.8,
            snippet="first snippet",
        ),
        SearchResult(
            conversation_id="conv-2",
            project_id="p",
            title="Title 2",
            created_at=now,
            updated_at=now,
            message_count=1,
            file_path="/tmp/2.jsonl",
            score=0.7,
            snippet="second snippet",
        ),
        SearchResult(
            conversation_id="conv-3",
            project_id="p",
            title="Title 3",
            created_at=now,
            updated_at=now,
            message_count=1,
            file_path="/tmp/3.jsonl",
            score=0.6,
            snippet="third snippet",
        ),
    ]

    reranked = engine._rerank("query text", results)

    assert [result.conversation_id for result in reranked[:2]] == ["conv-2", "conv-1"]
    assert reranked[2].conversation_id == "conv-3"
    assert calls == [[("query text", "first snippet"), ("query text", "second snippet")]]


@pytest.mark.unit
def test_search_engine_find_similar_vector_hits_uses_semantic_components(temp_search_dir: Path):
    cfg = Config.load()
    _prepare_search_dir(temp_search_dir, cfg)

    engine = SearchEngine(temp_search_dir, cfg)

    class _Embedder:
        def encode(self, text):
            assert text == "representative text"
            return np.array([0.1, 0.2, 0.3])

    class _FaissIndex:
        def search(self, embedding, k):
            assert embedding.shape == (1, 3)
            assert k == 3
            return (
                np.array([[0.15, 0.25, 0.35]], dtype=np.float32),
                np.array([[100, -1, 300]], dtype=np.int64),
            )

    engine.embedder = _Embedder()
    engine.faiss_index = _FaissIndex()

    hits = engine.find_similar_vector_hits("representative text", 3)

    assert [hit.vector_id for hit in hits] == [100, 300]
    assert [hit.distance for hit in hits] == pytest.approx([0.15, 0.35])


@pytest.mark.unit
def test_search_engine_find_similar_vector_hits_requires_faiss(temp_search_dir: Path):
    cfg = Config.load()
    _prepare_search_dir(temp_search_dir, cfg)

    engine = SearchEngine(temp_search_dir, cfg)
    engine.embedder = object()
    engine.ensure_faiss_loaded = lambda: None
    engine.ensure_embedder_loaded = lambda: None

    with pytest.raises(RuntimeError, match="FAISS index not available"):
        engine.find_similar_vector_hits("representative text", 3)


@pytest.mark.unit
def test_search_engine_find_similar_vector_hits_requires_embedder(temp_search_dir: Path):
    cfg = Config.load()
    _prepare_search_dir(temp_search_dir, cfg)

    engine = SearchEngine(temp_search_dir, cfg)
    engine.faiss_index = object()
    engine.ensure_faiss_loaded = lambda: None
    engine.ensure_embedder_loaded = lambda: None

    with pytest.raises(RuntimeError, match="Embedder not available"):
        engine.find_similar_vector_hits("representative text", 3)


@pytest.mark.unit
def test_search_engine_describe_capabilities_reflects_config_and_index(temp_search_dir: Path):
    cfg = Config.load()
    cfg.reranking.enabled = False
    _prepare_search_dir(temp_search_dir, cfg)

    engine = SearchEngine(temp_search_dir, cfg)
    capabilities = engine.describe_capabilities()

    assert capabilities.semantic_available is True
    assert capabilities.semantic_reason is None
    assert capabilities.reranking_available is False
    assert capabilities.reranking_reason == "Reranking is disabled"


@pytest.mark.unit
def test_search_engine_describe_capabilities_reflects_embedder_load_failure(
    monkeypatch: pytest.MonkeyPatch,
    temp_search_dir: Path,
):
    cfg = Config.load()
    _prepare_search_dir(temp_search_dir, cfg)

    monkeypatch.setattr(
        "searchat.core.search_engine.build_embedding_service",
        lambda _config: (_ for _ in ()).throw(
            EmbeddingModelUnavailable(f"Embedding model unavailable: {cfg.embedding.model}")
        ),
    )

    engine = SearchEngine(temp_search_dir, cfg)

    with pytest.raises(SemanticSearchUnavailable, match="Embedding model unavailable:"):
        engine.ensure_embedder_loaded()

    capabilities = engine.describe_capabilities()
    assert capabilities.semantic_available is False
    assert capabilities.semantic_reason == f"Embedding model unavailable: {cfg.embedding.model}"


@pytest.mark.unit
def test_search_engine_describe_capabilities_reflects_reranker_load_failure(
    monkeypatch: pytest.MonkeyPatch,
    temp_search_dir: Path,
):
    cfg = Config.load()
    cfg.reranking.enabled = True
    _prepare_search_dir(temp_search_dir, cfg)

    monkeypatch.setattr(
        "searchat.core.search_engine.build_reranking_service",
        lambda _config: (_ for _ in ()).throw(
            RerankingModelUnavailable(f"Reranking model unavailable: {cfg.reranking.model}")
        ),
    )

    engine = SearchEngine(temp_search_dir, cfg)

    now = datetime.now(timezone.utc)
    results = [
        SearchResult(
            conversation_id="conv-1",
            project_id="p",
            title="Title 1",
            created_at=now,
            updated_at=now,
            message_count=1,
            file_path="/tmp/1.jsonl",
            score=0.8,
            snippet="first snippet",
        )
    ]

    reranked = engine._rerank("query text", results)
    assert [result.conversation_id for result in reranked] == ["conv-1"]

    capabilities = engine.describe_capabilities()
    assert capabilities.reranking_available is False
    assert capabilities.reranking_reason == f"Reranking model unavailable: {cfg.reranking.model}"


@pytest.mark.unit
def test_search_engine_hybrid_falls_back_to_keyword_when_semantic_unavailable(
    monkeypatch: pytest.MonkeyPatch,
    temp_search_dir: Path,
):
    cfg = Config.load()
    _prepare_search_dir(temp_search_dir, cfg)

    engine = SearchEngine(temp_search_dir, cfg)
    now = datetime.now(timezone.utc)
    keyword_results = [
        SearchResult(
            conversation_id="conv-keyword",
            project_id="p",
            title="Keyword Result",
            created_at=now,
            updated_at=now,
            message_count=1,
            file_path="/tmp/1.jsonl",
            score=0.9,
            snippet="keyword snippet",
        )
    ]

    monkeypatch.setattr(engine, "_keyword_search", lambda _query, _filters: keyword_results)
    monkeypatch.setattr(
        engine,
        "_semantic_search",
        lambda _query, _filters: (_ for _ in ()).throw(SemanticSearchUnavailable("FAISS index not available")),
    )

    results = engine.search("query", mode=SearchMode.HYBRID, filters=SearchFilters())

    assert [result.conversation_id for result in results.results] == ["conv-keyword"]
    assert results.mode_used == SearchMode.KEYWORD.value


@pytest.mark.unit
def test_search_engine_semantic_mode_fails_closed_when_semantic_unavailable(
    monkeypatch: pytest.MonkeyPatch,
    temp_search_dir: Path,
):
    cfg = Config.load()
    _prepare_search_dir(temp_search_dir, cfg)

    engine = SearchEngine(temp_search_dir, cfg)
    monkeypatch.setattr(
        engine,
        "_semantic_search",
        lambda _query, _filters: (_ for _ in ()).throw(SemanticSearchUnavailable("FAISS index not available")),
    )

    with pytest.raises(RuntimeError, match="Search failed: FAISS index not available"):
        engine.search("query", mode=SearchMode.SEMANTIC, filters=SearchFilters())


@pytest.mark.unit
def test_search_engine_rerank_failure_returns_base_ranking(monkeypatch: pytest.MonkeyPatch, temp_search_dir: Path):
    cfg = Config.load()
    cfg.reranking.enabled = True
    cfg.reranking.top_k = 2
    _prepare_search_dir(temp_search_dir, cfg)

    class _Reranker:
        def predict(self, pairs):
            raise RuntimeError("cross-encoder unavailable")

    monkeypatch.setattr(
        "searchat.core.search_engine.build_reranking_service",
        lambda _config: _Reranker(),
    )

    engine = SearchEngine(temp_search_dir, cfg)
    now = datetime.now(timezone.utc)
    results = [
        SearchResult(
            conversation_id="conv-1",
            project_id="p",
            title="Title 1",
            created_at=now,
            updated_at=now,
            message_count=1,
            file_path="/tmp/1.jsonl",
            score=0.8,
            snippet="first snippet",
        ),
        SearchResult(
            conversation_id="conv-2",
            project_id="p",
            title="Title 2",
            created_at=now,
            updated_at=now,
            message_count=1,
            file_path="/tmp/2.jsonl",
            score=0.7,
            snippet="second snippet",
        ),
    ]

    reranked = engine._rerank("query text", results)

    assert [result.conversation_id for result in reranked] == ["conv-1", "conv-2"]
