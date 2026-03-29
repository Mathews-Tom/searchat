"""Unified search engine — 6-mode search with adaptive weight selection.

Implements the RetrievalBackend protocol.  Supports KEYWORD, SEMANTIC,
HYBRID, ADAPTIVE (query-classified weights), and stubs for CROSS_LAYER
and DISTILL (enabled in Phase 6).

Delegates to:
  - DuckDB FTS for BM25 keyword search
  - FAISS (legacy) or DuckDB HNSW for vector search
  - QueryClassifier for adaptive weight selection
  - ResultMerger (CombMNZ) for fusion
  - ProgressiveFallback for degraded-mode resilience
  - ConversationFilter for noise removal
"""
from __future__ import annotations

import hashlib
import logging
import time
from collections import OrderedDict
from pathlib import Path
from threading import Lock

import duckdb
import faiss
import numpy as np

from searchat.config import Config
from searchat.config.constants import FTS_STEMMER, FTS_STOPWORDS, QUERY_SYNONYMS
from searchat.core.conversation_filter import ConversationFilter
from searchat.core.progressive_fallback import ProgressiveFallback
from searchat.core.query_classifier import QueryClassifier
from searchat.core.query_parser import QueryParser
from searchat.core.result_merger import MergeConfig, ResultMerger
from searchat.core.filters import tool_sql_conditions
from searchat.models import (
    AlgorithmType,
    SearchFilters,
    SearchMode,
    SearchResult,
    SearchResults,
)
from searchat.services.retrieval_service import (
    RetrievalCapabilities,
    RerankingUnavailable,
    SemanticSearchUnavailable,
    SemanticVectorHit,
)
from searchat.services.semantic_model_service import (
    EmbeddingModelUnavailable,
    EmbeddingService,
    RerankingModelUnavailable,
    RerankingService,
    build_embedding_service,
    build_reranking_service,
)
from searchat.services.storage_contracts import read_index_metadata

log = logging.getLogger(__name__)


class AlgorithmNotAvailable(RuntimeError):
    """Raised when a requested algorithm type is not yet implemented."""


class UnifiedSearchEngine:
    """6-mode search engine implementing the RetrievalBackend protocol."""

    def __init__(self, search_dir: Path, config: Config | None = None) -> None:
        self.search_dir = search_dir
        self.faiss_index: faiss.Index | None = None
        self.embedder: EmbeddingService | None = None
        self.query_parser = QueryParser()

        self._init_lock = Lock()

        if config is None:
            config = Config.load()
        self.config = config

        self.conversations_dir = self.search_dir / "data" / "conversations"
        self.metadata_path = self.search_dir / "data" / "indices" / "embeddings.metadata.parquet"
        self.index_path = self.search_dir / "data" / "indices" / "embeddings.faiss"
        self.conversations_glob = str(self.conversations_dir / "*.parquet")

        # LRU cache
        self.cache_size = config.performance.query_cache_size
        self.result_cache: OrderedDict[str, tuple[SearchResults, float]] = OrderedDict()
        self.cache_ttl = 300

        # Search columns (exclude large 'messages' column)
        self.search_columns = [
            "conversation_id", "project_id", "file_path", "title",
            "created_at", "updated_at", "message_count", "full_text",
            "embedding_id", "file_hash", "indexed_at",
        ]

        self._validate_keyword_files()

        # Persistent in-memory DuckDB for FTS over parquet
        self._con = duckdb.connect(database=":memory:")
        try:
            mem_mb = int(config.performance.memory_limit_mb)
            self._con.execute(f"PRAGMA memory_limit='{mem_mb}MB'")
        except Exception as exc:
            log.warning("Failed to set DuckDB memory limit: %s", exc)

        # Lazy-loaded components
        self._reranker: RerankingService | None = None
        self._faiss_runtime_reason: str | None = None
        self._semantic_runtime_reason: str | None = None
        self._reranking_runtime_reason: str | None = None

        # Composable search components
        self._classifier = QueryClassifier(
            default_keyword_weight=config.ranking.keyword_weight,
            default_semantic_weight=config.ranking.semantic_weight,
        )
        self._merger = ResultMerger(MergeConfig(
            keyword_weight=config.ranking.keyword_weight,
            semantic_weight=config.ranking.semantic_weight,
            intersection_boost=config.ranking.intersection_boost,
            max_results=config.search.max_results,
        ))
        self._fallback = ProgressiveFallback()
        self._filter = ConversationFilter()

        # Build FTS index
        self._fts_ready = False
        try:
            self._build_fts_table()
            self._fts_ready = True
        except Exception as exc:
            log.warning("FTS table init deferred: %s", exc)

    # ------------------------------------------------------------------
    # RetrievalBackend protocol methods
    # ------------------------------------------------------------------

    def ensure_semantic_ready(self) -> None:
        with self._init_lock:
            self._ensure_metadata_ready_locked()
            self._ensure_faiss_loaded_locked()
            self._ensure_embedder_loaded_locked()

    def find_similar_vector_hits(self, text: str, k: int) -> list[SemanticVectorHit]:
        self._ensure_faiss_loaded()
        if self.faiss_index is None:
            raise SemanticSearchUnavailable("FAISS index not available")

        self._ensure_embedder_loaded()
        if self.embedder is None:
            raise SemanticSearchUnavailable("Embedder not available")

        query_embedding = np.asarray(self.embedder.encode(text), dtype=np.float32)
        distances, labels = self.faiss_index.search(
            query_embedding.reshape(1, -1), k,
        )

        valid_mask = labels[0] >= 0
        return [
            SemanticVectorHit(vector_id=int(vid), distance=float(dist))
            for vid, dist in zip(labels[0][valid_mask], distances[0][valid_mask])
        ]

    def describe_capabilities(self) -> RetrievalCapabilities:
        semantic_reason = self._semantic_unavailable_reason()
        reranking_reason = self._reranking_unavailable_reason()
        return RetrievalCapabilities(
            semantic_available=semantic_reason is None,
            reranking_available=reranking_reason is None,
            semantic_reason=semantic_reason,
            reranking_reason=reranking_reason,
        )

    def refresh_index(self) -> None:
        with self._init_lock:
            self.result_cache.clear()
            self.faiss_index = None
            self._faiss_runtime_reason = None
            self._semantic_runtime_reason = None
            self._reranking_runtime_reason = None
            try:
                self._build_fts_table()
                self._fts_ready = True
            except Exception as exc:
                self._fts_ready = False
                log.warning("FTS table rebuild failed: %s", exc)

    # ------------------------------------------------------------------
    # Main search dispatch
    # ------------------------------------------------------------------

    def search(
        self,
        query: str,
        mode: SearchMode = SearchMode.HYBRID,
        filters: SearchFilters | None = None,
        *,
        algorithm: AlgorithmType | None = None,
    ) -> SearchResults:
        """Execute a search with the specified mode or algorithm type.

        If `algorithm` is provided, it takes precedence over `mode`.
        """
        start_time = time.time()

        # Resolve algorithm type
        algo = algorithm or AlgorithmType.from_search_mode(mode)

        # Palace-powered search modes
        if algo in (AlgorithmType.CROSS_LAYER, AlgorithmType.DISTILL):
            if not self.config.palace.enabled:
                raise AlgorithmNotAvailable(
                    f"{algo.value} search requires palace.enabled = true in config"
                )

        # Wildcard → keyword only
        if query.strip() == "*":
            algo = AlgorithmType.KEYWORD

        # Cache check
        cache_key = self._get_cache_key(query, algo, filters)
        cached = self._get_from_cache(cache_key)
        if cached:
            cached.search_time_ms = (time.time() - start_time) * 1000
            return cached

        results, mode_used = self._dispatch(query, algo, filters)

        elapsed_ms = (time.time() - start_time) * 1000
        search_result = SearchResults(
            results=results,
            total_count=len(results),
            search_time_ms=elapsed_ms,
            mode_used=mode_used,
        )
        self._add_to_cache(cache_key, search_result)
        return search_result

    def _dispatch(
        self,
        query: str,
        algo: AlgorithmType,
        filters: SearchFilters | None,
    ) -> tuple[list[SearchResult], str]:
        """Dispatch to the appropriate search strategy."""
        if algo == AlgorithmType.KEYWORD:
            results = self._keyword_search(query, filters)
            return results, "keyword"

        if algo == AlgorithmType.SEMANTIC:
            results = self._semantic_search(query, filters)
            return results, "semantic"

        if algo == AlgorithmType.ADAPTIVE:
            return self._adaptive_search(query, filters)

        if algo == AlgorithmType.DISTILL:
            return self._distill_search(query, filters)

        if algo == AlgorithmType.CROSS_LAYER:
            return self._cross_layer_search(query, filters)

        # HYBRID (default)
        return self._hybrid_search(query, filters)

    def _hybrid_search(
        self,
        query: str,
        filters: SearchFilters | None,
    ) -> tuple[list[SearchResult], str]:
        """Hybrid search with progressive fallback."""
        def tier1() -> list[SearchResult]:
            keyword_results = self._keyword_search(query, filters)
            semantic_results = self._semantic_search(query, filters)
            merged = self._merger.merge(keyword_results, semantic_results)
            return self._rerank(query, merged)

        def tier2() -> list[SearchResult]:
            return self._keyword_search(query, filters)

        def tier3() -> list[SearchResult]:
            return self._keyword_search("*", filters)

        fb = self._fallback.execute([
            ("hybrid", tier1),
            ("keyword", tier2),
            ("browse", tier3),
        ])
        return fb.results, fb.mode_used

    def _adaptive_search(
        self,
        query: str,
        filters: SearchFilters | None,
    ) -> tuple[list[SearchResult], str]:
        """Adaptive search — uses QueryClassifier to select weights."""
        weights = self._classifier.classify(query)

        # If classifier says keyword-only, skip semantic
        if weights.semantic_weight == 0.0:
            results = self._keyword_search(query, filters)
            return results, f"adaptive:{weights.category.value}"

        def tier1() -> list[SearchResult]:
            keyword_results = self._keyword_search(query, filters)
            semantic_results = self._semantic_search(query, filters)
            merged = self._merger.merge(
                keyword_results,
                semantic_results,
                keyword_weight=weights.keyword_weight,
                semantic_weight=weights.semantic_weight,
            )
            return self._rerank(query, merged)

        def tier2() -> list[SearchResult]:
            return self._keyword_search(query, filters)

        fb = self._fallback.execute([
            (f"adaptive:{weights.category.value}", tier1),
            ("keyword", tier2),
        ])
        return fb.results, fb.mode_used

    # ------------------------------------------------------------------
    # Palace-powered search (DISTILL + CROSS_LAYER)
    # ------------------------------------------------------------------

    def _get_palace_query(self):
        """Lazy-load palace query engine."""
        if not hasattr(self, "_palace_query"):
            from searchat.palace.query import PalaceQuery

            data_dir = self.search_dir / "data"
            self._palace_query = PalaceQuery(
                data_dir=data_dir,
                config=self.config,
                embedder=self.embedder,
            )
        return self._palace_query

    def _distill_search(
        self,
        query: str,
        filters: SearchFilters | None,
    ) -> tuple[list[SearchResult], str]:
        """Search over distilled palace objects only."""
        pq = self._get_palace_query()
        project_ids = filters.project_ids if filters and filters.project_ids else None
        palace_results = pq.search_hybrid(
            query=query, limit=self.config.search.max_results, project_ids=project_ids,
        )

        results: list[SearchResult] = []
        for pr in palace_results:
            results.append(SearchResult(
                conversation_id=pr.conversation_id,
                project_id=pr.project_id,
                title=pr.exchange_core[:80],
                created_at=None,  # type: ignore[arg-type]
                updated_at=None,  # type: ignore[arg-type]
                message_count=pr.ply_end - pr.ply_start + 1,
                file_path="",
                score=pr.score,
                snippet=pr.specific_context[:300],
                message_start_index=pr.ply_start,
                message_end_index=pr.ply_end,
                exchange_id=pr.object_id,
                exchange_text=pr.exchange_core,
                bm25_score=pr.keyword_score,
                semantic_score=pr.semantic_score,
            ))

        return results, "distill"

    def _cross_layer_search(
        self,
        query: str,
        filters: SearchFilters | None,
    ) -> tuple[list[SearchResult], str]:
        """Cross-layer search: merge verbatim hybrid + palace distilled."""
        # Verbatim layer
        verbatim_results, _ = self._hybrid_search(query, filters)

        # Palace layer
        pq = self._get_palace_query()
        project_ids = filters.project_ids if filters and filters.project_ids else None
        palace_results = pq.search_hybrid(
            query=query, limit=50, project_ids=project_ids,
        )

        # Build palace results as SearchResult, keyed by conversation_id
        palace_by_conv: dict[str, SearchResult] = {}
        for pr in palace_results:
            sr = SearchResult(
                conversation_id=pr.conversation_id,
                project_id=pr.project_id,
                title=pr.exchange_core[:80],
                created_at=None,  # type: ignore[arg-type]
                updated_at=None,  # type: ignore[arg-type]
                message_count=pr.ply_end - pr.ply_start + 1,
                file_path="",
                score=pr.score,
                snippet=pr.specific_context[:300],
                message_start_index=pr.ply_start,
                message_end_index=pr.ply_end,
                exchange_id=pr.object_id,
                exchange_text=pr.exchange_core,
            )
            palace_by_conv[pr.conversation_id] = sr

        # Merge: boost verbatim results that also have palace hits
        seen_convs: set[str] = set()
        merged: list[SearchResult] = []
        for vr in verbatim_results:
            seen_convs.add(vr.conversation_id)
            palace_hit = palace_by_conv.get(vr.conversation_id)
            if palace_hit:
                vr.score *= 1.3  # cross-layer boost
                vr.exchange_text = palace_hit.exchange_text
            merged.append(vr)

        # Add palace-only results not in verbatim
        for conv_id, pr in palace_by_conv.items():
            if conv_id not in seen_convs:
                merged.append(pr)

        merged.sort(key=lambda r: r.score, reverse=True)
        return merged[:self.config.search.max_results], "cross_layer"

    # ------------------------------------------------------------------
    # Keyword search (BM25 over DuckDB FTS)
    # ------------------------------------------------------------------

    def _keyword_search(self, query: str, filters: SearchFilters | None) -> list[SearchResult]:
        if not self._fts_ready:
            try:
                self._build_fts_table()
                self._fts_ready = True
            except Exception as exc:
                log.warning("FTS unavailable: %s", exc)
                return []

        parsed = self.query_parser.parse(query)
        is_wildcard = parsed.original.strip() == "*"

        if is_wildcard:
            params: list[object] = []
            where_clause = self._where_from_filters(filters, params)
            sql = f"""
                SELECT conversation_id, project_id, title, created_at,
                       updated_at, message_count, file_path, full_text
                FROM conversations
                WHERE {where_clause}
                ORDER BY updated_at DESC
                LIMIT 100
            """
            rows = self._con.execute(sql, params).fetchall()
            return [
                SearchResult(
                    conversation_id=r[0], project_id=r[1], title=r[2],
                    created_at=r[3], updated_at=r[4], message_count=r[5],
                    file_path=r[6], score=0.0, snippet=(r[7] or "")[:200],
                )
                for r in rows
            ]

        all_terms = parsed.exact_phrases + parsed.must_include + parsed.should_include
        expanded_terms = list(all_terms)
        for term in all_terms:
            term_lower = term.lower()
            if term_lower in QUERY_SYNONYMS:
                expanded_terms.extend(QUERY_SYNONYMS[term_lower])

        fts_query = " ".join(expanded_terms)
        if not fts_query.strip():
            return []

        params = [fts_query]
        filter_params: list[object] = []
        where_clause = self._where_from_filters(filters, filter_params)
        params.extend(filter_params)

        exclude_conditions = ""
        for term in parsed.must_exclude:
            exclude_conditions += " AND NOT (full_text ILIKE '%' || ? || '%')"
            params.append(term)

        sql = f"""
            SELECT conversation_id, project_id, title, created_at,
                   updated_at, message_count, file_path, full_text,
                   fts_main_conversations.match_bm25(conversation_id, ?) AS score
            FROM conversations
            WHERE score IS NOT NULL AND {where_clause}{exclude_conditions}
            ORDER BY score DESC
            LIMIT 100
        """
        rows = self._con.execute(sql, params).fetchall()

        if not rows:
            return []

        all_terms_lower = [t.lower() for t in all_terms]
        results: list[SearchResult] = []
        for r in rows:
            title = r[2] or ""
            title_boost = 2.0 if any(t in title.lower() for t in all_terms_lower) else 1.0
            message_boost = float(np.log1p(r[5]))
            score = float(r[8]) * title_boost * message_boost

            results.append(
                SearchResult(
                    conversation_id=r[0], project_id=r[1], title=r[2],
                    created_at=r[3], updated_at=r[4], message_count=r[5],
                    file_path=r[6], score=score,
                    snippet=self._create_snippet(r[7] or "", parsed.original),
                    bm25_score=float(r[8]),
                )
            )

        results.sort(key=lambda x: x.score, reverse=True)
        return results

    # ------------------------------------------------------------------
    # Semantic search (FAISS vector)
    # ------------------------------------------------------------------

    def _semantic_search(self, query: str, filters: SearchFilters | None) -> list[SearchResult]:
        k = 100
        hits = []
        for order, hit in enumerate(self.find_similar_vector_hits(query, k)):
            hits.append((hit.vector_id, hit.distance, order))

        if not hits:
            return []

        values_clause = ", ".join(["(?, ?, ?)"] * len(hits))
        params: list[object] = []
        for vector_id, distance, order in hits:
            params.extend([vector_id, distance, order])

        params.append(str(self.metadata_path))
        params.append(self.conversations_glob)

        filter_params: list[object] = []
        where_clause = self._where_from_filters(filters, filter_params, table_alias="c")
        params.extend(filter_params)

        sql = f"""
        WITH hits(vector_id, distance, faiss_order) AS (
          VALUES {values_clause}
        )
        SELECT
          m.conversation_id,
          c.project_id,
          c.title,
          c.created_at,
          c.updated_at,
          c.message_count,
          c.file_path,
          m.chunk_text,
          m.message_start_index,
          m.message_end_index,
          hits.distance,
          hits.faiss_order
        FROM hits
        JOIN parquet_scan(?) AS m
          ON m.vector_id = hits.vector_id
        JOIN (
          SELECT conversation_id, project_id, title, created_at,
                 updated_at, message_count, file_path
          FROM parquet_scan(?)
          QUALIFY row_number() OVER (
              PARTITION BY conversation_id ORDER BY updated_at DESC NULLS LAST
          ) = 1
        ) AS c
          ON c.conversation_id = m.conversation_id
        WHERE {where_clause}
        QUALIFY row_number() OVER (PARTITION BY m.conversation_id ORDER BY hits.faiss_order) = 1
        ORDER BY hits.faiss_order
        """
        rows = self._con.execute(sql, params).fetchall()

        if not rows:
            return []

        results = []
        for (
            conversation_id, project_id, title, created_at, updated_at,
            message_count, file_path, chunk_text, message_start_index,
            message_end_index, distance, _faiss_order,
        ) in rows:
            score = 1.0 / (1.0 + float(distance))
            snippet_text = chunk_text or ""
            snippet = snippet_text[:300] + ("..." if len(snippet_text) > 300 else "")

            results.append(
                SearchResult(
                    conversation_id=conversation_id,
                    project_id=project_id,
                    title=title,
                    created_at=created_at,
                    updated_at=updated_at,
                    message_count=message_count,
                    file_path=file_path,
                    score=score,
                    snippet=snippet,
                    message_start_index=int(message_start_index),
                    message_end_index=int(message_end_index),
                    semantic_score=score,
                )
            )

        return results

    # ------------------------------------------------------------------
    # Reranking
    # ------------------------------------------------------------------

    def _rerank(self, query: str, results: list[SearchResult]) -> list[SearchResult]:
        if not self.config.reranking.enabled or not results:
            return results

        try:
            self._ensure_reranker_loaded()
        except Exception as exc:
            log.warning("Reranking unavailable: %s", exc)
            return results
        if self._reranker is None:
            return results

        top_k = min(self.config.reranking.top_k, len(results))
        candidates = results[:top_k]
        remainder = results[top_k:]

        pairs = [(query, r.snippet) for r in candidates]
        try:
            scores = self._reranker.predict(pairs)
        except Exception as exc:
            log.warning("Reranking failed: %s", exc)
            return results

        for result, score in zip(candidates, scores):
            result.score = float(score)

        candidates.sort(key=lambda r: r.score, reverse=True)
        return candidates + remainder

    # ------------------------------------------------------------------
    # FTS table management
    # ------------------------------------------------------------------

    def _build_fts_table(self) -> None:
        cols = ", ".join(self.search_columns)
        self._con.execute(f"""
            CREATE OR REPLACE TABLE conversations AS
            SELECT {cols}
            FROM parquet_scan('{self.conversations_glob}')
            QUALIFY row_number() OVER (
                PARTITION BY conversation_id ORDER BY updated_at DESC NULLS LAST
            ) = 1
        """)
        self._con.execute("INSTALL fts; LOAD fts;")
        self._con.execute(f"""
            PRAGMA create_fts_index(
                'conversations',
                'conversation_id',
                'full_text', 'title',
                stemmer='{FTS_STEMMER}',
                stopwords='{FTS_STOPWORDS}',
                overwrite=1
            )
        """)

    def close(self) -> None:
        if self._con:
            self._con.close()

    # ------------------------------------------------------------------
    # Filter / SQL helpers
    # ------------------------------------------------------------------

    def _where_from_filters(
        self,
        filters: SearchFilters | None,
        params: list[object],
        *,
        table_alias: str = "",
    ) -> str:
        prefix = f"{table_alias}." if table_alias else ""
        conditions = [f"{prefix}message_count > 0"]

        if filters:
            if filters.project_ids:
                placeholders = ",".join(["?"] * len(filters.project_ids))
                conditions.append(f"{prefix}project_id IN ({placeholders})")
                params.extend(filters.project_ids)

            if filters.tool:
                conditions.extend(tool_sql_conditions(filters.tool, prefix=table_alias))

            if filters.date_from:
                conditions.append(f"{prefix}updated_at >= ?")
                params.append(filters.date_from)

            if filters.date_to:
                conditions.append(f"{prefix}updated_at <= ?")
                params.append(filters.date_to)

            if filters.min_messages > 0:
                conditions.append(f"{prefix}message_count >= ?")
                params.append(int(filters.min_messages))

        return " AND ".join(conditions)

    # ------------------------------------------------------------------
    # Lazy initialization helpers
    # ------------------------------------------------------------------

    def _validate_keyword_files(self) -> None:
        if not self.conversations_dir.exists() or not any(self.conversations_dir.glob("*.parquet")):
            raise FileNotFoundError(f"No conversation parquet files found in {self.conversations_dir}")

    def _validate_index_metadata(self) -> None:
        metadata = read_index_metadata(self.search_dir)
        metadata.validate_compatible(embedding_model=self.config.embedding.model)

    def _ensure_metadata_ready_locked(self) -> None:
        self._validate_keyword_files()
        self._validate_index_metadata()
        if not self.metadata_path.exists():
            raise FileNotFoundError(
                f"Metadata parquet not found at {self.metadata_path}. Run indexer first."
            )

    def _ensure_faiss_loaded(self) -> None:
        with self._init_lock:
            self._ensure_faiss_loaded_locked()

    def _ensure_faiss_loaded_locked(self) -> None:
        self._ensure_metadata_ready_locked()
        if not self.index_path.exists():
            raise FileNotFoundError(
                f"FAISS index not found at {self.index_path}. Run indexer first."
            )
        if self.faiss_index is None:
            try:
                if getattr(self.config.performance, "faiss_mmap", False):
                    try:
                        flags = faiss.IO_FLAG_MMAP | faiss.IO_FLAG_READ_ONLY
                    except Exception as exc:
                        raise SemanticSearchUnavailable(
                            "FAISS mmap flags are not supported by this build"
                        ) from exc
                    self.faiss_index = faiss.read_index(str(self.index_path), flags)
                else:
                    self.faiss_index = faiss.read_index(str(self.index_path))
                self._faiss_runtime_reason = None
            except SemanticSearchUnavailable:
                raise
            except Exception as exc:
                self._faiss_runtime_reason = f"FAISS index unavailable: {exc}"
                raise SemanticSearchUnavailable(self._faiss_runtime_reason) from exc

    def _ensure_embedder_loaded(self) -> None:
        with self._init_lock:
            self._ensure_embedder_loaded_locked()

    def _ensure_embedder_loaded_locked(self) -> None:
        self._validate_index_metadata()
        if self.embedder is None:
            try:
                self.embedder = build_embedding_service(self.config)
                self._semantic_runtime_reason = None
            except EmbeddingModelUnavailable as exc:
                self._semantic_runtime_reason = str(exc)
                raise SemanticSearchUnavailable(str(exc)) from exc

    def _ensure_reranker_loaded(self) -> None:
        with self._init_lock:
            self._ensure_reranker_loaded_locked()

    def _ensure_reranker_loaded_locked(self) -> None:
        if not self.config.reranking.enabled:
            return
        if self._reranker is None:
            try:
                self._reranker = build_reranking_service(self.config)
                self._reranking_runtime_reason = None
            except RerankingModelUnavailable as exc:
                self._reranking_runtime_reason = str(exc)
                raise RerankingUnavailable(str(exc)) from exc

    def _semantic_unavailable_reason(self) -> str | None:
        if not self.metadata_path.exists():
            return "Metadata parquet not available"
        if not self.index_path.exists():
            return "FAISS index not available"
        if self.faiss_index is None and self._faiss_runtime_reason is not None:
            return self._faiss_runtime_reason
        if self.embedder is None and self._semantic_runtime_reason is not None:
            return self._semantic_runtime_reason
        return None

    def _reranking_unavailable_reason(self) -> str | None:
        if not self.config.reranking.enabled:
            return "Reranking is disabled"
        if self._reranker is None and self._reranking_runtime_reason is not None:
            return self._reranking_runtime_reason
        return None

    # ------------------------------------------------------------------
    # Cache
    # ------------------------------------------------------------------

    def _get_cache_key(self, query: str, algo: AlgorithmType, filters: SearchFilters | None) -> str:
        key_parts = [query, algo.value]
        if filters:
            if filters.project_ids:
                key_parts.append(f"projects:{','.join(filters.project_ids)}")
            if filters.date_from:
                key_parts.append(f"from:{filters.date_from.isoformat()}")
            if filters.date_to:
                key_parts.append(f"to:{filters.date_to.isoformat()}")
            if filters.min_messages > 0:
                key_parts.append(f"min_msgs:{filters.min_messages}")
        key_str = "|".join(key_parts)
        return hashlib.md5(key_str.encode()).hexdigest()

    def _get_from_cache(self, cache_key: str) -> SearchResults | None:
        if cache_key in self.result_cache:
            result, timestamp = self.result_cache[cache_key]
            if time.time() - timestamp < self.cache_ttl:
                self.result_cache.move_to_end(cache_key)
                return result
            del self.result_cache[cache_key]
        return None

    def _add_to_cache(self, cache_key: str, result: SearchResults) -> None:
        if len(self.result_cache) >= self.cache_size:
            self.result_cache.popitem(last=False)
        self.result_cache[cache_key] = (result, time.time())

    # ------------------------------------------------------------------
    # Snippet creation
    # ------------------------------------------------------------------

    def _create_snippet(self, full_text: str, query: str, length: int = 200) -> str:
        parsed = self.query_parser.parse(query)
        terms = [t.lower() for t in parsed.exact_phrases + parsed.must_include + parsed.should_include]

        if not terms:
            return full_text[:length] + ("..." if len(full_text) > length else "")

        capped_text = full_text[:50000]
        text_lower = capped_text.lower()

        best_score = -1
        best_start = 0

        step = max(1, length // 4)
        for start in range(0, max(1, len(capped_text) - length), step):
            window = text_lower[start:start + length]
            score = sum(window.count(term) for term in terms)
            if score > best_score:
                best_score = score
                best_start = start

        if best_score <= 0:
            return full_text[:length] + ("..." if len(full_text) > length else "")

        end = min(len(full_text), best_start + length)
        snippet = full_text[best_start:end]
        if best_start > 0:
            snippet = "..." + snippet
        if end < len(full_text):
            snippet = snippet + "..."
        return snippet
