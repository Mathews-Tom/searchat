"""Acceptance coverage for retrieval behavior in degraded Wave 3 states."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from searchat.config import Config
from searchat.core.search_engine import SearchEngine
from searchat.models import SearchMode, SearchResult
from searchat.services.retrieval_service import SemanticSearchUnavailable


def _prepare_search_dir(search_dir: Path, cfg: Config) -> None:
    conversations = search_dir / "data" / "conversations"
    conversations.mkdir(parents=True, exist_ok=True)
    (conversations / "c.parquet").write_bytes(b"")

    indices = search_dir / "data" / "indices"
    indices.mkdir(parents=True, exist_ok=True)
    (indices / "embeddings.metadata.parquet").write_bytes(b"")
    (indices / "embeddings.faiss").write_bytes(b"")
    (indices / "index_metadata.json").write_text(
        json.dumps(
            {
                "embedding_model": cfg.embedding.model,
                "format": "sentence_transformers_faiss",
                "schema_version": 1,
                "index_format_version": 1,
            }
        ),
        encoding="utf-8",
    )


def _keyword_result() -> SearchResult:
    from datetime import datetime, timezone

    now = datetime.now(timezone.utc)
    return SearchResult(
        conversation_id="conv-123",
        project_id="project-a",
        title="Keyword Match",
        created_at=now,
        updated_at=now,
        message_count=5,
        file_path="/tmp/conv-123.jsonl",
        score=0.8,
        snippet="keyword result",
    )


def test_hybrid_search_falls_back_to_keyword_mode_when_semantic_unavailable(temp_search_dir: Path):
    cfg = Config.load()
    _prepare_search_dir(temp_search_dir, cfg)
    engine = SearchEngine(temp_search_dir, cfg)
    engine._keyword_search = lambda _query, _filters: [_keyword_result()]
    engine._semantic_search = lambda _query, _filters: (_ for _ in ()).throw(
        SemanticSearchUnavailable("FAISS index not available")
    )
    engine._rerank = lambda _query, results: results

    result = engine.search("python", mode=SearchMode.HYBRID)

    assert result.mode_used == "keyword"
    assert [item.conversation_id for item in result.results] == ["conv-123"]


def test_semantic_search_stays_fail_closed_when_semantic_unavailable(temp_search_dir: Path):
    cfg = Config.load()
    _prepare_search_dir(temp_search_dir, cfg)
    engine = SearchEngine(temp_search_dir, cfg)
    engine._semantic_search = lambda _query, _filters: (_ for _ in ()).throw(
        SemanticSearchUnavailable("Embedder not available")
    )

    with pytest.raises(RuntimeError, match="Search failed: Embedder not available"):
        engine.search("python", mode=SearchMode.SEMANTIC)
